"""本地语言模型只解析草稿，不调用实验或调度执行接口。"""
from threading import Lock
from pathlib import Path
import hashlib
import os
from .config import DATA, QWEN
from .language_rules import validate_draft
from .language_prompt import PROMPT
from .language_normalization import ALIASES, decoded_fields
from .language_runtime import DTYPE, THREADS, ensure_memory
from .storage import read_json

_LOCK = Lock()
_MODEL = None
_TOKENIZER = None

def language_identity():
    metadata = read_json(QWEN / "verified.json", {})
    folder = Path(__file__).parent
    pipeline = hashlib.sha256(b"".join((folder / name).read_bytes() for name in ("language.py", "language_normalization.py", "language_rules.py", "language_runtime.py"))).hexdigest()
    return {"name": metadata.get("model", "Qwen2.5-0.5B-Instruct"),
            "revision": metadata.get("revision", "7ae557604adf67be50417f59c2c2f167def9a775"),
            "prompt_sha256": hashlib.sha256(PROMPT.encode()).hexdigest(), "pipeline_sha256": pipeline,
            "inference_dtype": DTYPE, "threads": THREADS}


def model_available():
    return (QWEN / "model.safetensors").is_file()


def language_policy():
    evaluation = read_json(DATA / "language-evaluation.json", {})
    identity = language_identity()
    matched = evaluation.get("identity") == identity
    count = evaluation.get("count", 0) if matched else 0
    exact = evaluation.get("model_exact_after_feedback", 0)
    passed = (count >= 24 and evaluation.get("holdout_count", 0) >= 16 and exact/max(count, 1) >= 0.9
              and evaluation.get("holdout_model_exact", 0)/max(evaluation.get("holdout_count", 0), 1) >= 0.9
              and evaluation.get("grounded_exact") == count and evaluation.get("identity") == identity)
    return {"mode": "local-qwen" if passed and model_available() else "template-fallback",
            "raw_exact": evaluation.get("raw_model_exact") if matched else None, "cases": count, "model": identity["name"],
            "after_feedback_exact": exact if matched else None,
            "reason": "本地模型尚未达到本版本启用线，使用模板和原文证据填表" if not passed else f"{count}条描述的模型提取及两轮合并通过；不合格候选明确回退模板，输出仍须人工确认"}


def parse_description(text, use_model=None):
    if not isinstance(text, str) or not text.strip() or len(text) > 500:
        raise ValueError("请输入 1 到 500 字的实验描述")
    if use_model is not None and not isinstance(use_model, bool):
        raise ValueError("use_model 必须是布尔值")
    grounded = validate_draft(text, {})
    proposal, method, error = {}, "template", None
    if use_model is None:
        use_model = language_policy()["mode"] == "local-qwen"
    raw, initial, normalized, retry, sources = None, None, {}, False, {}
    if use_model and model_available() and os.environ.get("AEROTOWER_DISABLE_LLM") != "1":
        try:
            raw = _generate(text)
            initial = raw
            valid_json = True
            try:
                proposal = decoded_fields(raw)
            except ValueError:
                valid_json, proposal = False, {}
            expected = {key: value for key, value in grounded["fields"].items() if key not in ("start_date", "days")}
            sources = {key: "initial" for key in proposal}
            if not valid_json or proposal != expected:
                # 反馈只给错误字段名，不把模板答案提供给模型，保留首轮输出供审计。
                feedback = {"missing": sorted(set(expected)-set(proposal)), "unsupported": sorted(set(proposal)-set(expected)),
                            "inconsistent": [key for key in proposal if key in expected and proposal[key] != expected[key]], "invalid_json": not valid_json}
                retry = True
                retained = {key: value for key, value in proposal.items() if key in expected and value == expected[key]}
                sources = {key: "initial" for key in retained}
                raw = _generate(text, initial, feedback)
                patch = decoded_fields(raw)
                proposal = {**retained, **patch}
                sources.update({key: "retry" for key in patch})
            normalized = proposal
            method = "local-qwen" if proposal == expected else "template-fallback"
        except (ValueError, RuntimeError, ImportError, OSError, MemoryError) as failure:
            error = str(failure)[:150]
            proposal = {}
            method = "template-fallback"
    result = validate_draft(text, proposal)
    if method == "template-fallback":
        result["warnings"].append("本地模型候选未完整通过原文核对，已明确回退模板；不是模型原始正确结果")
    result.update(method=method, model=language_identity()["name"] if raw is not None else None,
                  model_error=error, model_output=raw, initial_model_output=initial,
                  model_fields=normalized, model_field_sources=sources, retry_used=retry)
    return result


def _generate(text, previous=None, feedback=None):
    global _MODEL, _TOKENIZER
    with _LOCK:
        import torch
        from transformers import AutoModelForCausalLM, AutoTokenizer
        if _MODEL is None:
            ensure_memory("1.5B" in language_identity()["name"])
            torch.set_num_threads(THREADS)
            _TOKENIZER = AutoTokenizer.from_pretrained(str(QWEN), local_files_only=True, trust_remote_code=False)
            # 本机只有AVX2，完整试跑确认float32比强制bfloat16更快；不改变磁盘权重。
            dtype = getattr(torch, DTYPE)
            _MODEL = AutoModelForCausalLM.from_pretrained(str(QWEN), local_files_only=True,
                        trust_remote_code=False, dtype=dtype).eval()
        messages = [{"role": "system", "content": PROMPT}, {"role": "user", "content": text}]
        if previous:
            names = {value: key for key, value in ALIASES.items()}
            targets = list(dict.fromkeys(feedback["missing"]+feedback["inconsistent"]))
            correction = ("原始描述："+text+"。请只补提取这些字段："+"、".join(names.get(field, field) for field in targets)
                +"。用这些中文字段名作JSON键，值从原文摘录并保留单位。原来正确的字段已保存，其他字段不用输出，不要猜默认值。") if targets else "原来正确的字段已保存，无需补充。请只返回空JSON对象{}，不要重复无依据字段。"
            messages += [{"role": "assistant", "content": previous}, {"role": "user", "content": correction}]
        encoded = _TOKENIZER.apply_chat_template(messages, add_generation_prompt=True, tokenize=True,
                                                return_tensors="pt", return_dict=True)
        with torch.inference_mode():
            output = _MODEL.generate(**encoded, max_new_tokens=240, do_sample=False,
                                     pad_token_id=_TOKENIZER.eos_token_id)
        return _TOKENIZER.decode(output[0][encoded["input_ids"].shape[-1]:], skip_special_tokens=True)
