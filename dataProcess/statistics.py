import json
import operator
import sys

import xlrd3


class Flight:
    from_name = ""
    to_name = ""
    percent1 = 0
    percent2 = 0

    def __init__(self, num, start_str, end_str, from_code, to_code, flight_id, flying):
        self.num = num
        self.start_str = start_str
        self.end_str = end_str
        self.from_code = from_code
        self.to_code = to_code
        self.flight_id = flight_id
        self.flying = flying

    def getNum(self):
        return self.num

    def setPercent1(self, t):
        start = convertTime(self.start_str)
        end = convertTime(self.end_str)
        self.percent1 = (t - start) / (end - start)

    def setPercent2(self, t):
        start = convertTime(self.start_str)
        end = convertTime(self.end_str)
        self.percent2 = (t - start) / (end - start)

    def getPercent1(self):
        return self.percent1

    def getPercent2(self):
        return self.percent2

    def getFinishTime(self):
        return convertTime(self.end_str)

    # 后加的
    def getStartTime(self):
        return convertTime(self.start_str)

    def getFlightTime(self):
        return convertTime(self.end_str)-convertTime(self.start_str)

    def setFlying(self, fly):
        self.flying = fly
    # 后加的 完毕

    def setFromName(self, name):
        self.from_name = name

    def setToName(self, name):
        self.to_name = name

    def getFromCode(self):
        return self.from_code

    def getToCode(self):
        return self.to_code

    def toString(self):
        return str(self.num) + "->" + str(
            self.flight_id) + ": starts at " + self.start_str + " ends at " + self.end_str + " . The flight is from " + self.from_code + " to " + self.to_code


def getInput(flight_info, schedule):
    with open(flight_info, 'r') as load_info:
        info = json.load(load_info)
    with open(schedule, 'r') as load_schedule:
        data = json.load(load_schedule)
    flights = []
    # Initialize the first flight
    for i in range(len(data)):
        flights.append(Flight(
            i + 1,
            info['nodes'][str(data[i][0])]['TIME_DEPARTURE'],
            info['nodes'][str(data[i][0])]['TIME_ARRIVAL'],
            info['nodes'][str(data[i][0])]['DEPARTURE_AIRPORT'],
            info['nodes'][str(data[i][0])]['ARRIVAL_AIRPORT'],
            info['nodes'][str(data[i][0])]['FLIGHT_ID'],
            0))
        # print(flights[i].toString())
    start_loop(flights, info, data)


def convertTime(timeStr):
    year, month, day, hour, minute = timeStr.split(',')
    t = int(day) * 24 * 60 + int(hour) * 60 + int(minute) + int(month) * 30 * 24 * 60
        # + int(year) * 365 * 24 * 60
    return t

def start_loop(flights, info, data):
    distance = 60  # refresh per 5 min 原本是5
    leftTime = convertTime("2020, 11, 30, 0, 0")
    rightTime = convertTime("2020, 12, 6, 23, 59")
    curTime = leftTime
    pos = [0] * len(flights)
    day = 0
    hour = 0
    num = 0
    list_ = []
    while curTime <= rightTime:
        curTime += distance
        for i in range(len(flights)):
            if flights[i].getFinishTime() + distance <= curTime and pos[i] + 1 < len(data[i]):
                pos[i] += 1
                flights[i] = Flight(
                    i + 1,
                    info['nodes'][str(data[i][pos[i]])]['TIME_DEPARTURE'],
                    info['nodes'][str(data[i][pos[i]])]['TIME_ARRIVAL'],
                    info['nodes'][str(data[i][pos[i]])]['DEPARTURE_AIRPORT'],
                    info['nodes'][str(data[i][pos[i]])]['ARRIVAL_AIRPORT'],
                    info['nodes'][str(data[i][pos[i]])]['FLIGHT_ID'],
                    0)
            if flights[i].getStartTime() <= curTime < flights[i].getFinishTime() + distance:
                flights[i].setFlying(1)
            else:
                flights[i].setFlying(0)
            # flights[i].setPercent1(curTime)
            # flights[i].setPercent2(curTime - distance)
        lis = printCurResult(curTime, flights, info, data, hour, day)
        list_.append(lis)
        # if (day < 6):
        #     day = day + 1
        # else:
        #     day = 0
        #     hour = hour + 1
        if (hour < 23):
            hour = hour + 1
        else:
            hour = 0
            day = day + 1
        num = num + 1
    with open("statistics_new.json", "w") as f:
        json.dump(list_, f, ensure_ascii=False)


def printCurResult(num, flights, info, data, hour, day):
    alpha = {}
    data = xlrd3.open_workbook(r'.\飞机排班测试数据\（机场表）.xlsx')
    sheet = data.sheet_by_index(0)
    for i in range(sheet.nrows):
        alpha[sheet.cell(i, 0).value] = sheet.cell(i, 3).value
    # cmpfun = operator.attrgetter('percent2')
    # flights.sort(reverse=True, key=cmpfun)
    lis = []
    lis.append(hour)
    lis.append(day)
    # lis.append(hour)
    n = 0
    # value1 = []
    # value2 = []
    for i in range(len(flights)):
        if flights[i].flying == 1:
            n = n + 1
    lis.append(n)
    return lis
    # print(dic, end=",\n")
    # return dic


# src:

# main.py
# dataProcess.py
# output.json
# sichuan_big_graph
#       A319_C8Y124_big.json
#       A320_C6Y156_big.json

# python dataProcess.py ./sichuan_big_graph/A319_C8Y124_big.json ./output.json
if __name__ == "__main__":
    flight_info = './sichuan_big_graph/A319_C8Y124_big.json'
    schedule = './output.json'
    getInput(flight_info, schedule)
    # print(flights)
