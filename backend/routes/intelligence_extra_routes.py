"""客流、排班建议及固定模型复核接口。"""
from copy import deepcopy
from flask import Blueprint, request
from .intelligence_routes import handled, body_object
from ..services.intelligence.demand import forecast_demand
from ..services.intelligence.model_store import load_bundle
from ..services.intelligence.reviews import review_status, start_review
from ..services.intelligence.routing import recommend_routing

intelligence_extra_bp = Blueprint("intelligence_extra", __name__)


@intelligence_extra_bp.get("/demand")
@handled
def demand():
    bundle = load_bundle()
    if not bundle:
        raise ValueError("请先训练模型")
    return forecast_demand(bundle, request.args.get("source", "成都"),
                           int(request.args.get("horizon", 7)), request.args.get("start_date"))


@intelligence_extra_bp.get("/routing")
@handled
def routing():
    from .schedule_routes import _get_active_flights, _get_active_chains
    from ..state import get_filtered_mode
    schedule = deepcopy({"flights": _get_active_flights(), "chains": _get_active_chains()})
    if not schedule["flights"]:
        raise ValueError("请先生成或导入航班")
    return recommend_routing(load_bundle(), schedule, int(request.args.get("fleet", 100)), get_filtered_mode())


@intelligence_extra_bp.get("/reviews")
@handled
def reviews():
    return review_status()


@intelligence_extra_bp.get("/reviews/<identifier>")
@handled
def review(identifier):
    return review_status(identifier)


@intelligence_extra_bp.post("/reviews")
@handled
def new_review():
    body = body_object()
    if body.get("confirmed") is not True:
        raise ValueError("请先确认复核；演示模式将临时停用模型，需正常复核通过恢复")
    return start_review(body.get("mode", "regular"))
