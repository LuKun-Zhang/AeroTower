"""恢复策略基类"""


class BaseRecoveryStrategy:
    """所有恢复策略的基类。

    子类必须实现 can_apply、apply、evaluate 三个方法。
    """

    def __init__(self, current_schedule, impact_report):
        """
        Args:
            current_schedule: dict 当前排班状态
                {
                    'flights': [...],
                    'aircraft_assignments': {flight_id: aircraft},
                    'crew_assignments': {flight_id: [crew_members]},
                    'gate_assignments': {flight_id: gate_id},
                    'runway_assignments': {flight_id: runway_id},
                    'chains': [[flight, ...], ...],
                }
            impact_report: ImpactReport 影响分析报告
        """
        self.schedule = current_schedule
        self.impact = impact_report

    def can_apply(self):
        """判断此策略是否适用于当前异常场景。子类必须实现。"""
        raise NotImplementedError

    def apply(self):
        """执行恢复策略，返回变更方案 dict。
        子类必须实现。

        Returns:
            dict: {
                'flight_changes': [...],
                'aircraft_changes': [...],
                'crew_changes': [...],
                'gate_changes': [...],
                'runway_changes': [...],
                'side_effects': [...],
            }
        """
        raise NotImplementedError

    def evaluate(self, result):
        """评估恢复效果，返回 0~1 分数。子类必须实现。"""
        raise NotImplementedError

    @staticmethod
    def get_strategy_name():
        """返回策略名称，用于日志和前端展示"""
        return "BaseStrategy"
