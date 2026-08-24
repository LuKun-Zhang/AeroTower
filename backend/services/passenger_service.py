"""旅客查询服务"""

from .. import state


class PassengerService:
    """旅客查询：按 ID 查、按航班查"""

    def __init__(self):
        pass

    def get_by_id(self, pax_id):
        """按旅客 ID 查询"""
        index = state.get_passenger_index()
        if not index:
            return None
        return index.get(pax_id)

    def get_by_flight(self, flight_id):
        """按航班 ID 查询所有旅客"""
        index = state.get_passenger_index()
        if not index:
            return []
        result = []
        for pax_id, info in index.items():
            if info.get('flight_id') == flight_id:
                result.append(info)
        return result

    def get_flight_manifest(self, flight_id):
        """获取航班的完整座位分配表"""
        manifest = state.get_manifest_index()
        if not manifest:
            return {}
        return manifest.get(flight_id, {})

    def build_indexes(self, generated_data):
        """根据生成结果构建旅客索引和航班座位索引
        
        generated_data: FlightGenerator.generate() 的返回值
        """
        pax_index = {}
        manifest_index = {}

        for pax in generated_data.get('passengers', []):
            pax_index[pax['pax_id']] = pax

        for flight in generated_data.get('flights', []):
            manifest_index[flight['flight_id']] = {
                'flight_no': flight['flight_no'],
                'manifest': flight.get('passenger_manifest', {}),
                'pax_count': flight.get('pax_count', 0),
            }

        state.set_passenger_index(pax_index)
        state.set_manifest_index(manifest_index)
        return pax_index, manifest_index


# 单例
passenger_service = PassengerService()
