#!/usr/bin/env python
# coding=utf-8
from __future__ import print_function

import os
try:
	from urllib import urlencode, quote_plus
except ImportError:
	from urllib.parse import urlencode, quote_plus

try:
	import urllib2 as wdf_urllib
	from cookielib import CookieJar
except ImportError:
	import urllib.request as wdf_urllib
	from http.cookiejar import CookieJar

import re
import time
import xml.dom.minidom
import json
import sys
import math
import subprocess
import ssl
import thread

DEBUG = False

MAX_GROUP_NUM = 35  # 每组人数
INTERFACE_CALLING_INTERVAL = 30  # 接口调用时间间隔, 间隔太短容易出现"操作太频繁", 会被限制操作半小时左右
MAX_PROGRESS_LEN = 50

QRImagePath = os.path.join(os.getcwd(), 'qrcode.jpg')

tip = 0
uuid = ''

base_uri = ''
redirect_uri = ''
push_uri = ''

skey = ''
wxsid = ''
wxuin = ''
pass_ticket = ''
deviceId = 'e000000000000000'

BaseRequest = {}
replyDict = {}
nameDict = {}

ContactList = []
My = []
SyncKey = []


toUserName = ''

try:
	xrange
	range = xrange
except:
	# python 3
	pass


def responseState(func, BaseResponse):
	ErrMsg = BaseResponse['ErrMsg']
	Ret = BaseResponse['Ret']
	if DEBUG or Ret != 0:
		print('func: %s, Ret: %d, ErrMsg: %s' % (func, Ret, ErrMsg))

	if Ret != 0:
		return False

	return True


def getRequest(url, data=None):
	try:
		data = data.encode('utf-8')
	except:
		pass
	finally:
		return wdf_urllib.Request(url=url, data=data)


def getUUID():
	global uuid

	url = 'https://login.weixin.qq.com/jslogin'
	params = {
		'appid': 'wx782c26e4c19acffb',
		'fun': 'new',
		'lang': 'zh_CN',
		'_': int(time.time()),
	}

	request = getRequest(url=url, data=urlencode(params))
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	# window.QRLogin.code = 200; window.QRLogin.uuid = "oZwt_bFfRg==";
	regx = r'window.QRLogin.code = (\d+); window.QRLogin.uuid = "(\S+?)"'
	pm = re.search(regx, data)

	code = pm.group(1)
	uuid = pm.group(2)

	if code == '200':
		return True

	return False


def showQRImage():
	global tip

	url = 'https://login.weixin.qq.com/qrcode/' + uuid
	params = {
		't': 'webwx',
		'_': int(time.time()),
	}

	request = getRequest(url=url, data=urlencode(params))
	response = wdf_urllib.urlopen(request)

	tip = 1

	f = open(QRImagePath, 'wb')
	f.write(response.read())
	f.close()

	if sys.platform.find('darwin') >= 0:
		subprocess.call(['open', QRImagePath])
	elif sys.platform.find('linux') >= 0:
		subprocess.call(['xdg-open', QRImagePath])
	else:
		os.startfile(QRImagePath)

	print('请使用微信扫描二维码以登录')


def waitForLogin():
	global tip, base_uri, redirect_uri, push_uri

	url = 'https://login.weixin.qq.com/cgi-bin/mmwebwx-bin/login?tip=%s&uuid=%s&_=%s' % (
		tip, uuid, int(time.time()))

	request = getRequest(url=url)
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	# window.code=500;
	regx = r'window.code=(\d+);'
	pm = re.search(regx, data)

	code = pm.group(1)

	if code == '201':  # 已扫描
		print('成功扫描,请在手机上点击确认以登录')
		tip = 0
	elif code == '200':  # 已登录
		print('正在登录...')
		regx = r'window.redirect_uri="(\S+?)";'
		pm = re.search(regx, data)
		redirect_uri = pm.group(1) + '&fun=new'
		base_uri = redirect_uri[:redirect_uri.rfind('/')]

		# push_uri与base_uri对应关系(排名分先后)(就是这么奇葩..)
		services = [
			('wx2.qq.com', 'webpush2.weixin.qq.com'),
			('qq.com', 'webpush.weixin.qq.com'),
			('web1.wechat.com', 'webpush1.wechat.com'),
			('web2.wechat.com', 'webpush2.wechat.com'),
			('wechat.com', 'webpush.wechat.com'),
			('web1.wechatapp.com', 'webpush1.wechatapp.com'),
		]
		push_uri = base_uri
		for (searchUrl, pushUrl) in services:
			if base_uri.find(searchUrl) >= 0:
				push_uri = 'https://%s/cgi-bin/mmwebwx-bin' % pushUrl
				break

		# closeQRImage
		if sys.platform.find('darwin') >= 0:  # for OSX with Preview
			os.system("osascript -e 'quit app \"Preview\"'")
	elif code == '408':  # 超时
		pass
	# elif code == '400' or code == '500':

	return code


def login():
	global skey, wxsid, wxuin, pass_ticket, BaseRequest, deviceId

	request = getRequest(url=redirect_uri)
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	doc = xml.dom.minidom.parseString(data)
	root = doc.documentElement

	for node in root.childNodes:
		if node.nodeName == 'skey':
			skey = node.childNodes[0].data
		elif node.nodeName == 'wxsid':
			wxsid = node.childNodes[0].data
		elif node.nodeName == 'wxuin':
			wxuin = node.childNodes[0].data
		elif node.nodeName == 'pass_ticket':
			pass_ticket = node.childNodes[0].data
		elif node.nodeName == 'DeviceID':
			deviceId = node.childNodes[0].data

	# print('skey: %s, wxsid: %s, wxuin: %s, pass_ticket: %s' % (skey, wxsid,
	# wxuin, pass_ticket))

	if not all((skey, wxsid, wxuin, pass_ticket)):
		return False

	BaseRequest = {
		'Uin': int(wxuin),
		'Sid': wxsid,
		'Skey': skey,
		'DeviceID': deviceId,
	}

	return True


def webwxinit():

	url = base_uri + \
		'/webwxinit?pass_ticket=%s&skey=%s&r=%s' % (
			pass_ticket, skey, int(time.time()))
	params = {
		'BaseRequest': BaseRequest
	}

	request = getRequest(url=url, data=json.dumps(params))
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read()

	if DEBUG:
		f = open(os.path.join(os.getcwd(), 'webwxinit.json'), 'wb')
		f.write(data)
		f.close()

	data = data.decode('utf-8', 'replace')

	# print(data)

	global ContactList, My, SyncKey, toUserName
	dic = json.loads(data)
	ContactList = dic['ContactList']
	My = dic['User']
	SyncKey = dic['SyncKey']

	for i, val in enumerate(ContactList):
		# print(ContactList[i]['Alias'])
		if ContactList[i]['Alias'].find('orly') != -1:
			toUserName = ContactList[i]['UserName']
	state = responseState('webwxinit', dic['BaseResponse'])
	return state


def webwxgetcontact():
	print ('Fetching Contacts')
	url = base_uri + \
		'/webwxgetcontact?pass_ticket=%s&skey=%s&r=%s' % (
			pass_ticket, skey, int(time.time()))

	request = getRequest(url=url)
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read()

	if DEBUG:
		f = open(os.path.join(os.getcwd(), 'webwxgetcontact.json'), 'wb')
		f.write(data)
		f.close()

	# print(data)
	data = data.decode('utf-8', 'replace')

	dic = json.loads(data)
	MemberList = dic['MemberList']
	# print('MemberList')
	#for i, val in enumerate(MemberList):
	#	print(i)
	#	print(MemberList[i]['NickName'])
	# 倒序遍历,不然删除的时候出问题..
	SpecialUsers = ["newsapp", "fmessage", "filehelper", "weibo", "qqmail", "tmessage", "qmessage", "qqsync", "floatbottle", "lbsapp", "shakeapp", "medianote", "qqfriend", "readerapp", "blogapp", "facebookapp", "masssendapp",
					"meishiapp", "feedsapp", "voip", "blogappweixin", "weixin", "brandsessionholder", "weixinreminder", "wxid_novlwrv3lqwv11", "gh_22b87fa7cb3c", "officialaccounts", "notification_messages", "wxitil", "userexperience_alarm"]
	for i in range(len(MemberList) - 1, -1, -1):
		Member = MemberList[i]
		if Member['VerifyFlag'] & 8 != 0:  # 公众号/服务号
			MemberList.remove(Member)
		elif Member['UserName'] in SpecialUsers:  # 特殊账号
			MemberList.remove(Member)
		#elif Member['UserName'].find('@@') != -1:  # 群聊
		#	MemberList.remove(Member)
		#elif Member['UserName'] == My['UserName']:  # 自己
		#	MemberList.remove(Member)

	return MemberList

def matchUserNameAndNickName(MemberList):
	print('matching names')	
	global nameDict
	for member in MemberList:
		# print(member['UserName'] + " -> " + member['NickName'])
		nameDict[member['UserName']] = member['NickName']
	if not My['UserName'] in nameDict.keys():
		nameDict[My['UserName']] = My['NickName']
	
def createChatroom(UserNames):
	MemberList = [{'UserName': UserName} for UserName in UserNames]

	url = base_uri + \
		'/webwxcreatechatroom?pass_ticket=%s&r=%s' % (
			pass_ticket, int(time.time()))
	params = {
		'BaseRequest': BaseRequest,
		'MemberCount': len(MemberList),
		'MemberList': MemberList,
		'Topic': '',
	}

	request = getRequest(url=url, data=json.dumps(params))
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	dic = json.loads(data)
	ChatRoomName = dic['ChatRoomName']
	MemberList = dic['MemberList']
	DeletedList = []
	BlockedList = []
	for Member in MemberList:
		if Member['MemberStatus'] == 4:  # 被对方删除了
			DeletedList.append(Member['UserName'])
		elif Member['MemberStatus'] == 3:  # 被加入黑名单
			BlockedList.append(Member['UserName'])

	state = responseState('createChatroom', dic['BaseResponse'])

	return ChatRoomName, DeletedList, BlockedList


def deleteMember(ChatRoomName, UserNames):
	url = base_uri + \
		'/webwxupdatechatroom?fun=delmember&pass_ticket=%s' % (pass_ticket)
	params = {
		'BaseRequest': BaseRequest,
		'ChatRoomName': ChatRoomName,
		'DelMemberList': ','.join(UserNames),
	}

	request = getRequest(url=url, data=json.dumps(params))
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	dic = json.loads(data)

	state = responseState('deleteMember', dic['BaseResponse'])
	return state


def addMember(ChatRoomName, UserNames):
	url = base_uri + \
		'/webwxupdatechatroom?fun=addmember&pass_ticket=%s' % (pass_ticket)
	params = {
		'BaseRequest': BaseRequest,
		'ChatRoomName': ChatRoomName,
		'AddMemberList': ','.join(UserNames),
	}

	request = getRequest(url=url, data=json.dumps(params))
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	dic = json.loads(data)
	MemberList = dic['MemberList']
	DeletedList = []
	BlockedList = []
	for Member in MemberList:
		if Member['MemberStatus'] == 4:  # 被对方删除了
			DeletedList.append(Member['UserName'])
		elif Member['MemberStatus'] == 3:  # 被加入黑名单
			BlockedList.append(Member['UserName'])

	state = responseState('addMember', dic['BaseResponse'])

	return DeletedList, BlockedList


def syncKey():
	SyncKeyItems = ['%s_%s' % (item['Key'], item['Val'])
					for item in SyncKey['List']]
	SyncKeyStr = '|'.join(SyncKeyItems)
	return SyncKeyStr


def syncCheck():
	url = push_uri + '/synccheck?'
	params = {
		'skey': BaseRequest['Skey'],
		'sid': BaseRequest['Sid'],
		'uin': BaseRequest['Uin'],
		'deviceId': BaseRequest['DeviceID'],
		'synckey': syncKey(),
		'r': int(time.time()),
	}

	request = getRequest(url=url + urlencode(params))
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)

	# window.synccheck={retcode:"0",selector:"2"}
	regx = r'window.synccheck={retcode:"(\d+)",selector:"(\d+)"}'
	pm = re.search(regx, data)

	retcode = pm.group(1)
	selector = pm.group(2)

	return selector

def getSendToNameFromUserName(userName):
	print('getSentToName')
	print(userName)
	sendToName = ''
	if userName.find('@@') != -1:
		regx = r'@@\w+ '
		m = re.search(regx, userName)
		if m:
			sendToName = m.group(0).replace(' ', '')
	else:
		sendToName = userName
	return sendToName

def getAtNameFromUserName(userName):
	print('getAtName')
	print(userName)
	atName = ''
	if userName.find('@@') != -1:
		regx = r' @\w+'
		m = re.search(regx, userName)
		if m:
			atName = m.group(0).replace(' ', '')
	else:
		atName = userName
	return atName

def webwxsync(selector):
	global SyncKey, My, replyDict, nameDict

	url = base_uri + '/webwxsync?lang=zh_CN&skey=%s&sid=%s&pass_ticket=%s' % (
		BaseRequest['Skey'], BaseRequest['Sid'], quote_plus(pass_ticket))
	params = {
		'BaseRequest': BaseRequest,
		'SyncKey': SyncKey,
		'rr': ~int(time.time()),
	}
	# print(params)
	request = getRequest(url=url, data=json.dumps(params))
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')

	# print(data)
	
	#if selector != 2:
	#	return
	dic = json.loads(data)
	msgList = dic['AddMsgList']
	
	for msg in msgList:
		if msg['Content']:
			fromName = msg['FromUserName']
			if fromName.find('@@') != -1:
				regx = r'@\w+:'
				m = re.search(regx, msg['Content'])
				if m:
					fromName = fromName + ' ' + m.group(0)
		
			if msg['Content'].find('msg') == -1:
				replyDict[fromName] = msg['Content']
			else:
				print(msg['FromUserName'] + ": " + msg['Content'].replace('<br/>', '\n'))
	
	printDict(replyDict)

	SyncKey = dic['SyncKey']

	state = responseState('webwxsync', dic['BaseResponse'])
	return state

def heartBeatLoop():
	while True:
		selector = syncCheck()
		if selector != '0':
			webwxsync()
		time.sleep(15)

def fetchGroupMemberNickNames(groupList):
	print ("Fetching group contacts")
	global nameDict
	url = base_uri + '/webwxbatchgetcontact?type=ex&r=%s&lang=zh_CH&pass_ticket=%s' % (
		int(time.time()), quote_plus(pass_ticket))
	for i, val in enumerate(groupList):
		groupDict = {}
		groupDict['ChatRoomId'] = ''
		groupDict['UserName'] = val
		groupList[i] = groupDict
	print ('Conv groupList to groupDict')
	print (groupList)
	params = {
	'BaseRequest': BaseRequest,
	'Count' : len(groupList),
	'List' : groupList
	}
	stri = json.dumps(params, encoding='UTF-8', ensure_ascii=False)
	request = getRequest(url=url, data=stri)
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')
	jData = json.loads(data)
	contactList = jData['ContactList']
	for i, val in enumerate(contactList):
		groupMemberList = val['MemberList']
		for j, val in enumerate(groupMemberList):
			nameDict[val['UserName']] = val['NickName']

def genNameDict():
	global nameDict
	memberList = webwxgetcontact()
	matchUserNameAndNickName(memberList)
	groupList = []
	for i in range(len(memberList) - 1, -1, -1):
		Member = memberList[i]
		if Member['UserName'].find('@@') != -1:  # 群聊
			groupList.append(Member['UserName'])
	fetchGroupMemberNickNames(groupList)
	print ('nameDict : ')	
	printDict(nameDict)

def sendMessage(toName, text):
	
	url = base_uri + '/webwxsendmsg?lang=zh_CN&pass_ticket=%s' % (
		quote_plus(pass_ticket))
	# print('send message to ' + toName + ': ' + text)
	# print(url)
	global My
	Msg = {
	'Type' : 1,
	u'Content' : text.encode('utf-8'),
	'FromUserName' : My['UserName'],
	'ToUserName' : toName,
	'LocalID' : str(int(time.time())),
	'ClientMsgId' : str(int(time.time()))
	}
	params = {
	'BaseRequest': BaseRequest,
	u'Msg' : Msg
	}
	stri = json.dumps(params, encoding='UTF-8', ensure_ascii=False)
	# print(stri)
	request = getRequest(url=url, data=stri)
	request.add_header('ContentType', 'application/json; charset=UTF-8')
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')
	# print (json.loads(data))

def getSimSimiResponse(text):
	simKey = ''
	text = text.replace(' ', ',')
	url = 'http://sandbox.api.simsimi.com/request.p?key=%s&lc=ch&ft=1.0&text=%s' % (
		simKey, text)
	print ('Sent to Simsimi')
	print (url)
	request = getRequest(url=url)
	response = wdf_urllib.urlopen(request)
	data = response.read().decode('utf-8', 'replace')
	res = json.loads(data)
	if res['result'] != 100:
		return 'Status: ' + res['result'] + ' -> ' + res['msg']
	else:
		if 'response' in res.keys():		
			return res['response']
		else:
			return 'WARNING: status 100 yet no response received, perhaps daily limit reached.'

def processReplyDict():
	global replyDict, nameDict
	for key in replyDict.keys():
		sendToName = getSendToNameFromUserName(key)
		atName = getAtNameFromUserName(key)
		ignoreMsg = False
		if sendToName.find('@@') != -1:
			if atName in nameDict.keys():
				content = '@' + nameDict[atName] + ','
			else:
				content = ''
			if replyDict[key].find('@AI') == -1:
				ignoreMsg = True;
		else:
			content = ''
		if not ignoreMsg:
			replyDict[key] = re.sub(r'\[\w+\]', '', replyDict[key])
			text = getSimSimiResponse(replyDict[key])
			print ('SimSimi response got: ' + text)
			content = content + text
			print ('Prepare to send: ' + content)
			print ('to user name: ' + sendToName)
			sendMessage(sendToName, content)
		del replyDict[key]

def printDict(dic):
	if not dic:
		print ('Dict is empty')
	else:
		for key in dic.keys():
			print ('[' + key + '] = ' + dic[key])

def main():

	try:
		# ssl._create_default_https_context = ssl._create_unverified_context

		opener = wdf_urllib.build_opener(
			wdf_urllib.HTTPCookieProcessor(CookieJar()))
		opener.addheaders = [
			('User-agent', 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/44.0.2403.125 Safari/537.36')]
		wdf_urllib.install_opener(opener)
	except:
		pass
	
	reload(sys)
	sys.setdefaultencoding('utf-8')
	if not getUUID():
		print('获取uuid失败')
		return

	print('正在获取二维码图片...')
	showQRImage()
	time.sleep(1)

	while waitForLogin() != '200':
		pass

	os.remove(QRImagePath)

	if not login():
		print('登录失败')
		return

	if not webwxinit():
		print('初始化失败')
		return


	genNameDict()
	
	# for key in nameDict:
	#	print (nameDict[key] + ': ' + key)
	# print('开启心跳线程')
	# thread.start_new_thread(heartBeatLoop, ())

	# print('-----------Start Monitoring------------')
	global toUserName
	while True:
		# print('Try Send Chinese')
		# sendMessage(toUserName, '发送中文')
		selector = syncCheck()
		if selector != '0':
			print (selector)
			webwxsync(selector)
		processReplyDict()
		time.sleep(5)



class UnicodeStreamFilter:

	def __init__(self, target):
		self.target = target
		self.encoding = 'utf-8'
		self.errors = 'replace'
		self.encode_to = self.target.encoding

	def write(self, s):
		if type(s) == str:
			s = s.decode('utf-8')
		s = s.encode(self.encode_to, self.errors).decode(self.encode_to)
		self.target.write(s)

if sys.stdout.encoding == 'cp936':
	sys.stdout = UnicodeStreamFilter(sys.stdout)

if __name__ == '__main__':

	main()
