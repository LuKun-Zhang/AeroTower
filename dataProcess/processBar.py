# name:Shuo
# time:2022/5/27 12:00

import json
import operator
import sys

import xlrd3

colors = ["#a0e85b", "#1b511d", "#c6edc5", "#0f144c", "#967ff2", "#803673", "#bf11af", "#edcbde", "#1a119b", "#918ea2", "#445082", "#fa79f5", "#8c2efc", "#c479a3", "#faf679", "#829951", "#30972e", "#3a2006", "#e9ad6f", "#84541a", "#ed4b04", "#8f0f1b"]


class Flight:
    from_name = ""
    to_name = ""
    percent1 = 0
    percent2 = 0

    def __init__(self, num, start_str, end_str, from_code, to_code, flight_id, flying, color):
        self.num = num
        self.start_str = start_str
        self.end_str = end_str
        self.from_code = from_code
        self.to_code = to_code
        self.flight_id = flight_id
        self.flying = flying
        self.color = color

    def getNum(self):
        return self.num

    def setPercent1(self, t):
        start = convertTime(self.start_str)
        end = convertTime(self.end_str)
        self.percent1 = (t - start) / (end - start)

    # def setPercent2(self, t):
    #     start = convertTime(self.start_str)
    #     end = convertTime(self.end_str)
    #     self.percent2 = (t - start) / (end - start)

    def getPercent1(self):
        return self.percent1

    # def getPercent2(self):
    #     return self.percent2

    def getFinishTime(self):
        return convertTime(self.end_str)

    # 后加的
    def getStartTime(self):
        return convertTime(self.start_str)

    def getFlightTime(self):
        return convertTime(self.end_str)-convertTime(self.start_str)

    def setFlying(self, fly):
        self.flying = fly

    def getColor(self):
        return self.color
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
    # list = []
    # for i in range(len(data)):
    #     list.append(len(data[i]))
    # print(list)
    # Initialize the first flight
    for i in range(len(data)):
        flights.append(Flight(
            i + 1,
            info['nodes'][str(data[i][0])]['TIME_DEPARTURE'],
            info['nodes'][str(data[i][0])]['TIME_ARRIVAL'],
            info['nodes'][str(data[i][0])]['DEPARTURE_AIRPORT'],
            info['nodes'][str(data[i][0])]['ARRIVAL_AIRPORT'],
            info['nodes'][str(data[i][0])]['FLIGHT_ID'],
            0,
            colors[i]))
        # print(flights[i].toString())
    start_loop(flights, info, data)


def convertTime(timeStr):
    year, month, day, hour, minute = timeStr.split(',')
    # if month == 11:
    #     t = int(hour) * 60 + int(minute)
    #     print(t)
    # else:
    #     t = int(day) * 24 * 60 + int(hour) * 60 + int(minute)
    t = int(day) * 24 * 60 + int(hour) * 60 + int(minute) + int(month) * 30 * 24 * 60
        # + int(year) * 365 * 24 * 60
    return t


def findTime(info, data):
    first_flight_time_list = []
    last_flight_time_list = []
    lastTime = 0
    for i in range(len(data)):
        last_flight_time_list.append(info['nodes'][str(data[i][len(data[i]) - 1])]['TIME_ARRIVAL'])
        first_flight_time_list.append(info['nodes'][str(data[i][0])]['TIME_DEPARTURE'])
    for i in range(len(data)):
        if convertTime(last_flight_time_list[i]) > lastTime:
            lastTime = convertTime(last_flight_time_list[i]) + 60
    firstTime = lastTime
    for i in range(len(data)):
        if convertTime(first_flight_time_list[i]) < firstTime:
            firstTime = convertTime(first_flight_time_list[i])
    return firstTime, lastTime


def start_loop(flights, info, data):
    distance = 60  # refresh per 5 min 原本是5
    leftTime = 30 * 24 * 60 + 0 * 60 + 0 + 11 * 30 * 24 * 60
    rightTime = 7 * 24 * 60 + 0 * 60 + 0 + 12 * 30 * 24 * 60
    curTime = leftTime
    pos = [0] * len(flights)
    num = 0
    list_ = []
    list_item = []
    # for i in range(7):
    #     for j in range(24):
    #         list_item = []
    #         list_item.append(i)
    #         list_item.append(j)
    #         count = 0
    #         for k in range(len(flights)):
    #             year, month, day, hour, minute = flights[k].split(',')
    #             if day == 30:
    #                 day = 0
    list = []
    while curTime <= rightTime:
        # 这个时间里有几个航班
        count = 0
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
                    0,
                    colors[i])
            if flights[i].getStartTime() <= curTime < flights[i].getFinishTime() + distance:
                flights[i].setFlying(1)
                count += 1
            else:
                flights[i].setFlying(0)
            flights[i].setPercent1(curTime)
            # flights[i].setPercent2(curTime - distance)
        list.append(count)
        # lis = printCurResult(curTime, flights, info, data)
        # list_.append(lis)
        num = num + 1
        curTime += distance
    print(len(list))
    print(list)
    # with open("procBarWithNumber.json", "w") as f:
    #     json.dump(list_, f, ensure_ascii=False)


def printCurResult(num, flights, info, data):
    alpha = {}
    data = xlrd3.open_workbook(r'.\飞机排班测试数据\（机场表）.xlsx')
    sheet = data.sheet_by_index(0)
    for i in range(sheet.nrows):
        alpha[sheet.cell(i, 0).value] = sheet.cell(i, 3).value
    cmpfun = operator.attrgetter('percent1')
    temp_flights = sorted(flights, reverse=True, key=cmpfun)
    # 一个时间片
    dic = {}
    # 片里有两个list
    title = []
    data = []
    for i in range(len(temp_flights)):
        if temp_flights[i].flying == 1:
            # print(temp_flights[i].num)
            titltStr = str(temp_flights[i].num) + "." + alpha[temp_flights[i].getFromCode()] + "-" + alpha[temp_flights[i].getToCode()]
            title.append(titltStr)
            dataItem = {}
            percent = min(temp_flights[i].getPercent1(), 1.0)
            dataItem['value'] = int(100 * percent)
            colorItem = {}
            colorItem["color"] = temp_flights[i].getColor()
            dataItem['itemStyle'] = colorItem
            data.append(dataItem)
        # print(temp_flights[i].toString())
    dic["title"] = title
    dic["data"] = data
    # print(dic)
    return dic
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
    # airline = './out.json'
    getInput(flight_info,schedule)
    # print(flights)

