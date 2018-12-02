# -*- coding:utf-8 -*-
import requests
from requests.packages.urllib3.exceptions import InsecureRequestWarning
requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

import pymysql.cursors
from re import compile
import sys


class MySQL:
    def __init__(self):
        self._cursor = None
        self._connect = None

    def connect(self, host, user, password, database, port):
        self._connect = pymysql.connect(
            host=host,
            user=user,
            port=port,
            password=password,
            database=database)
        self._cursor = self._connect.cursor()

    def close(self):
        if self._cursor:
            self._cursor.close()
        if self._connect:
            self._connect.close()

    def query(self, sql):
        try:
            self._cursor.execute(sql)
            return self._cursor.fetchall()
        except pymysql.ProgrammingError as e:
            return e

    def execute(self, sql):
        try:
            self._cursor.execute(sql)
            self._connect.commit()
        except pymysql.ProgrammingError as e:
            self._connect.rollback()
            return e


def _checkFormat(text, data):
    """
    text 传入需要检测的text
    data 传入字典数据
    """
    if not data: return text

    if isinstance(text, str):
        if "{" in text:
            try:
                return text.format(**data)
            except KeyError:
                return text

    if isinstance(text, dict):
        new_dict = {}
        for k, v in text.items():
            try:
                if "{" in k:
                    k = k.format(**data)
                if "{" in v:
                    v = v.format(**data)
            except KeyError:
                new_dict[k] = v
            new_dict[k] = v
        return new_dict
    return text


def getHttpTypeItemID(query, httptype, httpid):
    result = {}
    if httptype == "httpstep":
        sql = "select * from httpstepitem where httpstepid=%s;" % httpid
    elif httptype == "httptest":   
        sql = "select * from httptestitem where httptestid=%s;" % httpid
    sql_result = query(sql)
    if isinstance(sql_result,tuple):
        for _ in sql_result:
            result[_[3]] = _[2] 
    return result



def getHttpTestField(query, httptestid):
    result = {"Variables": {}, "Headers": {}}
    sql = "select * from httptest_field where httptestid=%s;" % httptestid
    sql_result = query(sql)
    if isinstance(sql_result, tuple):
        for _ in sql_result:
            if _[2] == 1:
                result["Variables"][_[3].strip('{').strip('}')] = _[4]
            elif _[2] == 0:
                result["Headers"][_[3]] = _[4]
    return result


def getHttpStepField(query, httpstepid):
    result = {
        "Variables": {},
        "Headers": {},
        "PostFields": {},
        "QueryFields": {}
    }
    sql = "select * from httpstep_field where httpstepid=%s;" % httpstepid
    sql_result = query(sql)
    if isinstance(sql_result, tuple):
        for _ in sql_result:
            if _[2] == 1:
                result["Variables"][_[3].strip('{').strip('}')] = _[4]
            elif _[2] == 0:
                result["Headers"][_[3]] = _[4]
            elif _[2] == 2:
                result["PostFields"][_[3]] = _[4]
            elif _[2] == 3:
                result["QueryFields"][_[3]] = _[4]
    return result


def getHttpTestInfo(query, itemid):
    result_dict = {}
    item_key = ("httptestitemid", "httptestid", "agent", "no", "url",
                "timeout", "required", "follow_redirects", "posts",
                "status_codes", "post_type", "httpstepid")
    sql = """
    SELECT h.httptestitemid, h.httptestid, t.agent, s.no, s.url, s.timeout, 
           s.required, s.follow_redirects, s.posts, s.status_codes, s.post_type,
           s.httpstepid
    FROM httptestitem h
	INNER JOIN httptest t ON h.httptestid = t.httptestid
	INNER JOIN httpstep s ON s.httptestid = t.httptestid
    WHERE h.itemid = "%s";
    """ % itemid
    sql_result = query(sql)
    if isinstance(sql_result, tuple):
        result_dict = {
            _[3]: {k: v
                   for k, v in zip(item_key, _)}
            for _ in sql_result
        }
    return result_dict

def insertData(exe,table,itemid,value):
    from time import time
    sql = "insert into %s values ('%s','%s','%s','0')" % (table,itemid,int(time()),value)
    exe(sql)

def myRequests(request,
               url,
               headers,
               post_dict={},
               requests_function="GET",
               timeout="15",
               required_string="",
               status_code=200,
               allow_redirects=True,
               variables={}):

    result_dict = {
        "StatusCode": 0,
        "ErrorMessage": "",
        "ResponseTime": 0,
        "Status": 0
    }
    new_headers = {
        "User-Agent":
        "Mozilla/5.0 (Windows NT 6.1; WOW64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/38.0.2125.104 Safari/537.36"
    }
    new_headers.update(headers)
    try:
        if requests_function == "GET":
            r = request.get(
                url=url,
                headers=new_headers,
                verify=False,
                timeout=timeout,
                allow_redirects=allow_redirects)

        elif requests_function == "POST":
            r = request.post(
                url=url,
                headers=new_headers,
                data=post_dict,
                verify=False,
                timeout=timeout,
                allow_redirects=allow_redirects)

    except (requests.exceptions.TooManyRedirects, requests.exceptions.Timeout,
            requests.exceptions.HTTPError, requests.exceptions.ConnectionError,
            requests.exceptions.RequestException) as e:
        result_dict["ErrorMessage"] = "%s (%s)" % (e, __file__)
    else:
        result_dict["StatusCode"] = r.status_code
        result_dict["ResponseTime"] = r.elapsed.total_seconds()
        result_dict["test"] = "test"
        # 判断是否包含字符
        if required_string:
            content_re = compile(r"%s" % required_string)
            content = content_re.findall(r.text)
            if not content:
                result_dict[
                    "ErrorMessage"] = "required pattern \"%s\" was not found on %s (%s)" % (
                        required_string, url, __file__)
                result_dict["Status"] = 1

        web_result = r.text
        if variables:
            for k, v in variables.items():
                if "regex:" in v:
                    v = ''.join(v.split("regex:")[1:])
                    v_re = compile(r"%s" % v)
                    result_dict[k] = v_re.findall(web_result)[0]
                else:
                    result_dict[k] = v

        # 判断状态码
        if result_dict["StatusCode"] != status_code:
            result_dict[
                "ErrorMessage"] = "response code \"%s\" did not match any of the required status codes \"%s\" (%s)" % (
                    result_dict["StatusCode"], status_code, __file__)
            result_dict["Status"] = 1
    finally:
        request.close()
        return result_dict


if __name__ == "__main__":
    # 获取告警item
    ITEMID = int(sys.argv[1])

    # 读取Zabbix配置文件
    CONFIG = "/tmp/zabbix.conf"

    f = open(CONFIG)
    configList = [
        _.split()[0] for _ in f.readlines() if not _.startswith('#')
        if "=" in _
    ]
    configDict = { _.split("=")[0]: _.split("=")[1] for _ in configList }

    # 实例化mysql
    m = MySQL()
    m.connect(
    host=configDict.get("DBHost","localhost"),
    user=configDict.get("DBUser","zabbix"),
    password=configDict.get("DBPassword","zabbix"),
    port=int(configDict.setdefault("DBPort",3306)),
    database=configDict.get("DBName","zabbix"))

    # 实例化requests
    r = requests.Session()

    httpTestInfo = getHttpTestInfo(m.query, ITEMID)
    if httpTestInfo:
        queryDict   = {}
        totalStatus = 0
        httpTestID  = 0
        lastError   = None

        for k, v in httpTestInfo.items():
            httpTestID  = v.get("httptestid", "")
            httpStepID  = v.get("httpstepid", "")
            httpStepURL = v.get("url", "")

            httpTestAGENT       = v.get("agent", "")
            httpStepPostType    = v.get("post_type", "")
            httpStepStatusCode  = 200 if not v.get("status_codes",
                                                  "") else v["status_codes"]

            httpStepTimeout     = int(v.get("timeout", 0).split("s")[0])
            httpStepRequired    = v.get("required", "")
            httpStepFollow      = False if v.get("follow_redirects",
                                            "") == 0 else True

            # 字段信息
            httpStepField = getHttpStepField(m.query, httpStepID)
            httpTestField = getHttpTestField(m.query, httpTestID)

            # 变量信息
            httpStepVariables = httpStepField["Variables"]
            httpTestVariables = httpTestField["Variables"]
            queryDict.update(httpStepVariables)
            queryDict.update(httpTestVariables)

            # 头部信息
            httpStepHeaders = httpStepField["Headers"]
            httpTestHeaders = httpTestField["Headers"]
            httpTestHeaders.update(httpStepHeaders)

            # Post数据
            httpStepPostDict = httpStepField["PostFields"]

            # 请求参数
            url         = _checkFormat(httpStepURL, queryDict)
            headers     = _checkFormat(httpTestHeaders, queryDict)
            post_dict   = _checkFormat(
                httpStepPostDict,
                queryDict) if v.get("post_type") == 1 else _checkFormat(
                    v.get("posts", ""), queryDict)
            requests_function   = "POST" if post_dict else "GET"
            required_string     = httpStepRequired
            status_code         = httpStepStatusCode
            timeout             = httpStepTimeout
            allow_redirects     = httpStepFollow
            variables           = _checkFormat(httpStepVariables, queryDict)

            testStepReult = myRequests(
                r,
                url=url,
                headers=headers,
                required_string=required_string,
                timeout=timeout,
                status_code=status_code,
                allow_redirects=allow_redirects,
                variables=variables,
                post_dict=post_dict,
                requests_function=requests_function,
            )

            # Test信息
            totalStatus += testStepReult["Status"]
            if testStepReult["ErrorMessage"]:
                lastError = testStepReult["ErrorMessage"]
    
            queryDict.update(testStepReult)
            httpStepItemID = getHttpTypeItemID(m.query,"httpstep",httpStepID)
    
            # 插入场景返回状态码与返回时间
            insertData(m.execute,"history_uint",httpStepItemID[0],testStepReult["StatusCode"])
            insertData(m.execute,"history",httpStepItemID[1],testStepReult["ResponseTime"])

        httpTestItemID = getHttpTypeItemID(m.query,"httptest",httpTestID)
        insertData(m.execute,"history_uint",httpTestItemID[3],totalStatus)
        if lastError:
            insertData(m.execute,"history_str",httpTestItemID[4],lastError)