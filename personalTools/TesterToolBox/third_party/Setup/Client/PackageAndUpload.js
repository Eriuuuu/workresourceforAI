/**
 * @author luoxj
 * @fileoverview 集群跑测试客户端，将release和test打包上传到ftp
 */
// 引入 events 模块
var events = require('events');
// 创建 eventEmitter 对象
var eventEmitter = new events.EventEmitter();
var fs = require('fs');
const pump = require('pump');
var http = require('http');
var querystring = require('querystring');
var lz4 = require('lz4');
//将压缩包上传ftp
var Client = require('ftp');
var Path = require('path');
//压缩
const compressing = require('compressing');
var sleep = require('system-sleep');
var progress = require('cli-progress');
require('source-map-support').install();


const bar = new progress.Bar({}, progress.Presets.legacy);
var barLength = 500;
var barMultiple = 1;

if (process.argv == undefined || process.argv == '' || process.argv == null || process.argv.length < 8) {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

let releaseSrc = process.argv[2];
if (releaseSrc == undefined || releaseSrc == null || releaseSrc == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

let testSrc = process.argv[3];
if (testSrc == undefined || testSrc == null || testSrc == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

let server = process.argv[4];
if (server == undefined || server == null || server == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

let testCollectionIniPath = process.argv[5];
if (testCollectionIniPath == undefined || testCollectionIniPath == null || testCollectionIniPath == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

let selectedTestCollectionDirs = process.argv[6];
if (selectedTestCollectionDirs == undefined || selectedTestCollectionDirs == null || selectedTestCollectionDirs == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}
let selectedTestCollectionDirArr = selectedTestCollectionDirs.split('/');

let testGlobalConfigIniFilePath = process.argv[7];
if (testGlobalConfigIniFilePath == undefined || testGlobalConfigIniFilePath == null || testGlobalConfigIniFilePath == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

let runtestExePath = process.argv[8];
if (runtestExePath == undefined || runtestExePath == null || runtestExePath == '') {
	alert("before error.");
	throw SyntaxError();
	alert("after error.");
}

//设置上传ftp的服务器信息
let configFile = './Config.json';
let ftpConfigJson = JSON.parse(fs.readFileSync(configFile));
let ftpOptions = ftpConfigJson.ftpOptions;
let ftpOptionLogs = ftpConfigJson.ftpOptionLogs;
// 自动化使用
let runAutomation = ftpConfigJson.RunAutomation;
//ftp的保存package的路径
let ftpPath = ftpConfigJson.ftpPath;
var ftpInfo = {};
ftpInfo.releaseFtpOption = ftpOptions[0];
ftpInfo.testFtpOption = ftpOptions[0];
ftpInfo.ftpPath = ftpPath;


//获取本机的hostname
let os = require('os');
let userName = os.userInfo().username.toLowerCase();
//获得本机的ip
let ip = getIPAdress();
//获得当前时间
var today = new Date();
String.prototype.replaceAll = function (s1, s2) {
	return this.replace(new RegExp(s1, 'gm'), s2);
};
let now = today.toLocaleString();
now = now.replaceAll(' ', ':').replace(new RegExp(/(:)/g), '-');
let ftpPackagePrefixPath = userName + '_' + ip + '_' + now;
let uploadCount = 0;

if(IsReleaseMode(releaseSrc)){
	//将runtestPackage移动到tests的thirdparty目录下
	removeRuntestPackageToTests();
}


//判断提交的包是不是release模式，禁止提交debug模式
function IsReleaseMode(releaseSrc){
	var releaseBasename = Path.basename(releaseSrc);
	if(releaseBasename == "x64Debug"){
		console.log("禁止提交debug模式，请使用release模式");
		return false;
	}
	return true;
}

  //将runtestPackage移动到tests的thirdparty目录下
  function removeRuntestPackageToTests(){
	let packageStream = unpack(runtestExePath,["Logs.temp"]);
	let packageNameInGbmp = 'RunTestPackage';
	let packageNameInToolServices = Path.basename(runtestExePath);
	let packagePath = Path.join(testSrc,'thirdparty\\RunTestPackage');
	if(runAutomation == 1) {
		let clientStream = unpack(runtestExePath+"\\..\\Client",["Logs.temp"]);
		let clientPath = Path.join(testSrc,'thirdparty\\Client');
		compressing.tar.uncompress(clientStream,clientPath)
		.then((data)=>{
			if(!isThirdpartyFolderValid()){
					return;
			}
		})
		.catch(err=>{
			console.log('error');
		});
	}
	
	compressing.tar.uncompress(packageStream,packagePath)
	.then((data)=>{
	   if(!isThirdpartyFolderValid()){
			return;
	   }
	   packageAndUploadTest();
	   packageAndUploadRelease();
	})
	.catch(err=>{
		console.log('error');
	});
  }

  //判断Tests文件夹下thirdparty文件夹是否完整，不完整的话禁止提交任务
  function isThirdpartyFolderValid(){
	let thirdpartyPath = Path.join(testSrc,'thirdparty');
	//1、首先保证Tests文件夹里有thirdparty文件夹
	let testFolderList = fs.readdirSync(testSrc);
	let isExits = contains(testFolderList,"thirdparty");
	if(!isExits){
		console.log("1请保证Tests文件夹下的thirdparty文件夹合法");
		return false;
	}
	//2、再保证thirdparty文件夹里含有Nodejs和RunTestPackage文件夹
	let thirdpartyFolderList = fs.readdirSync(thirdpartyPath);
	isExits = (contains(thirdpartyFolderList,"Nodejs")) && (contains(thirdpartyFolderList,"RunTestPackage"));
	if(!isExits){
		console.log("2请保证Tests文件夹下的thirdparty文件夹合法");
		return false;
	}
	return true;
  }

  //打包
 function unpack(folderPath,excludePaths){
	let tarStream = new compressing.tar.Stream();
	let files = fs.readdirSync(folderPath);
	files.forEach(function(file){
		if(!contains(excludePaths,file)){
			tarStream.addEntry(Path.join(folderPath,file));
		}
	});
	console.log("unpack done");
	return tarStream;
};

//判断元素是否在数组中
function contains(arr, obj) {
    var i = arr.length;
    while (i--) {
        if (arr[i] === obj) {
            return true;
        }
    }
    return false;
}
 
//压缩并上传
//压缩test
//查看test文件夹下的文件目录，过滤掉不用压缩的文件(Stream 接口：可以动态添加任意文件、文件夹到一个 tar stream 对象中)
function packageAndUploadTest(){
	fs.readdir(testSrc, function (err, files) {
		if (err) {
			console.log("test read dir error");
			throw err;
		}
		const testTarStream = new compressing.tar.Stream();
		let testEncoder = lz4.createEncoderStream();
		files.forEach(function (file) {
			if (file != 'RunTest_New.exe.lnk') {
				let path = testSrc + '\\' + file;
				let stat = fs.lstatSync(path);
				if (stat.isDirectory()) {
					if (selectedTestCollectionDirArr.indexOf(file) != -1 || file == 'thirdparty') {
						testTarStream.addEntry(testSrc + '\\' + file);
					}
				} else {
					testTarStream.addEntry(testSrc + '\\' + file);
				}
			}
		});

		var testUploadClient = new Client();
		var testUploadClientBackUp = new Client();
		console.log('start upload test package');
		//主ftp
		testUploadClient.connect(ftpOptions[0]);
		testUploadClient.on('error',function(error){
			testUploadClientBackUp.connect(ftpOptions[1]);
			ftpInfo.testFtpOption = ftpOptions[1];
		});
		testUploadClient.on('ready', function () {
			ftpOpteration(testUploadClient,"test.lz4",testTarStream,testEncoder);
		});
		//备用ftp
		testUploadClientBackUp.on('error',function(error){
			console.log("error: " + error);
			console.log("主备ftp全部连接失败，请稍后重试");
			return;
		});
		testUploadClientBackUp.on('ready',function(){
			ftpOpteration(testUploadClientBackUp,"test.lz4",testTarStream,testEncoder);
		});
	});
}


//压缩release(Stream 接口：可以动态添加任意文件、文件夹到一个 tar stream 对象中)
function packageAndUploadRelease(){
	fs.readdir(releaseSrc, function (err, files) {
		if (err) {
			console.log("read release dir error");
			throw err;
		}
		const releaseTarStream = new compressing.tar.Stream();
		let releaseEncoder = lz4.createEncoderStream();
		files.forEach(function (file) {
			if (file.toString().lastIndexOf('.pdb') == -1 && file != 'Logs') {
				if (file == "sdk") {
					let sdkDir = releaseSrc + "\\" + file;
					fs.readdir(sdkDir, function (err, files_) {
						if (err) {
							throw err;
						}
						files_.forEach(function (file_) {
							if (file_ != "Logs" && file_.toString().lastIndexOf(".pdb") == -1) {
								let tempPath = sdkDir + "\\" + file_;
								let stat_ = fs.lstatSync(tempPath);
								if (stat_.isFile()) {
									releaseTarStream.addEntry(tempPath, {
										relativePath: file + "\\" + file_
									});
								}
								if (stat_.isDirectory()) {
									releaseTarStream.addEntry(tempPath, {
										relativePath: file
									});
								}
							}
						});
					});
				} else {
					releaseTarStream.addEntry(releaseSrc + '\\' + file);
				}
			}
		});

		let releaseUploadClient = new Client();
		let releaseUploadClientBackUp = new Client();
		console.log('start upload release package');
		//主ftp
		releaseUploadClient.connect(ftpOptions[0]);
		releaseUploadClient.on('error',function(error){
			releaseUploadClientBackUp.connect(ftpOptions[1]);
			ftpInfo.releaseFtpOption = ftpOptions[1];
		});
		releaseUploadClient.on('ready', function () {
			ftpOpteration(releaseUploadClient,"release.lz4",releaseTarStream,releaseEncoder);
		});
		//备用ftp
		releaseUploadClientBackUp.on('error',function(error){
			console.log("error: " + error);
			console.log("主备ftp全部连接失败，请稍后重试");
			return;
		});
		releaseUploadClientBackUp.on('ready',function(){
			ftpOpteration(releaseUploadClientBackUp,"release.lz4",releaseTarStream,releaseEncoder);
		});
	});
}


//当package上传成功后，发送http请求
eventEmitter.on('send_http', function () {
	uploadCount++;
	let body = {};
	body.cases = [];
	body.ftpInfo = {};
	body.globalConfig = {};
	if (uploadCount == 2) {
		uploadCount = 0;
		//读取测试集的ini文件
		let testCollectionIniData = fs.readFileSync(testCollectionIniPath);
		if (testCollectionIniData == undefined || testCollectionIniData.toString().length == 0) {
			return;
		}
		//对读取的data数据解析
		let testCollectionIniDataJsonArray = parseINIString(testCollectionIniData.toString());

		//读取RunTest Ui界面全局配置的ini文件
		let testGlobalConfigIniData = fs.readFileSync(testGlobalConfigIniFilePath);
		if (testGlobalConfigIniData == undefined || testGlobalConfigIniData.toString().length == 0) {
			return;
		}
		let testGlobalConfigIniDataJsonArray = parseINIString(testGlobalConfigIniData.toString());

		//读取Client的版本号
		let versionConfigPath = './VersionConfig.json';
		if(!fs.existsSync(versionConfigPath)){
			console.log('\n您的Client缺少版本信息，请确保您的Client完整以后再使用');
			return;
		}
		let clientVersion = JSON.parse(fs.readFileSync(versionConfigPath));

		//获得服务器信息
		let serverConfigFile = './ServerConfig.json';
		let serverConfig = JSON.parse(fs.readFileSync(serverConfigFile));
		let serverConfigContent = serverConfig.ServerOption;
		let index = 0;
		for(let i = 0;i < serverConfigContent.length;i++){
			if(serverConfigContent[i].host == server){
				index = i;
				break;
			}
		}
		
		//post请求体数据
		body.userName = userName;
		body.ip = ip;
		body.email = userName + '@glodon.com';
		body.ftpURL = ftpPackagePrefixPath + '_release.lz4';
		body.ftpInfo = ftpInfo;
		body.cases = testCollectionIniDataJsonArray;
		body.globalConfig = testGlobalConfigIniDataJsonArray[0];
		body.clientVersion = clientVersion.Version;
		//正则表达式验证
		// ip是否合法
		let ipTest = /^((2[0-4]\d|25[0-5]|[01]?\d\d?)\.){3}(2[0-4]\d|25[0-5]|[01]?\d\d?)$/;
		if (!ipTest.test(ip)) {
			console.log('ip不合法');
			return;
		}
		//邮箱是否合法
		let emailTest = /^([a-z0-9_\.-]+)@([\da-z\.-]+)\.([a-z\.]{2,6})$/i;
		if (!emailTest.test(body.email)) {
			console.log('email不合法');
			return;
		}
		//ftpURL是否合法
		let ftpURLTest = new RegExp(
			'([a-z0-9_\\.-]+?)_' +
			'((2[0-4]\\d|25[0-5]|[01]?\\d\\d?)\\.){3}(2[0-4]\\d|25[0-5]|[01]?\\d\\d?)' +
			'_(?:19|20)[0-9][0-9]-(?:(?:[1-9])|(?:1[0-2]))-(?:(?:[1-2]?[1-9])|(?:[1-3]' +
			'[0-1]))-(?:(?:[0-2][0-3])|(?:[0-1][0-9]))-[0-5][0-9]-[0-5][0-9]_release.lz4$',
			'i'
		);

		if (!ftpURLTest.test(body.ftpURL)) {
			console.log('ftpURL不合法');
			return;
		}
		let requestApi = '';
		if(runAutomation == 1){
			requestApi = '/submitJobByAuto.do';
		}else {
			requestApi = '/uploadJob.do';
		}
		let options = {
			host: serverConfigContent[index].host,
			port: serverConfigContent[index].port,
			path: requestApi,
			method: 'POST',
			headers: {
				'content-type': 'application/json'
			}
		};
		var req = http.request(options, function (res) {
			let responseFromServer = '';
			res.setEncoding('utf8');
			res.on('data', function (data) {
				console.log('\ndata:' + data);
				responseFromServer = data;
			});
			res.on('end', function (err) {
				if (err) {
					console.error(err);
				}
				if(responseFromServer.startsWith("Your job has been received")){
					if(runAutomation == 1) {
						console.log('\nSTATUS: ' + res.statusCode);
						console.log(responseFromServer);
						// 写入本地文件
						fs.writeFileSync("JobId.txt", responseFromServer);
					}else {
						console.log('\nSTATUS: ' + res.statusCode);
						console.log('success and complete.');
					}
					
				}
				process.exit();
			});
		});

		req.on('error', function (e) {
			console.log('upload Error: ' + e.message);
			throw e;
		});

		req.write(JSON.stringify(body));
		req.end();
	}else{
		//创建任务在ftp上的log文件夹
		let ftpURL = ftpPackagePrefixPath + '_release.lz4';
		let logsFolderName = getFolderName(ftpURL);
		createUserLogsFolderOnFtp(logsFolderName);
	}
});

//上传压缩包到ftp
function ftpOpteration(ftpClient,packSuffix,tarStream,encoder){
	ftpClient.cwd(ftpPath, function (err, currentDir) {
		if (err) {
			console.error("cwd error");
			throw err;
		}
		bar.start(barLength, 0);
		let ftpPath_ = ftpPackagePrefixPath + '_' + packSuffix;
		let uploadFileStream = tarStream.pipe(encoder);
		let uploadedMutiple = 0;
		uploadFileStream.on('data', function (buffer) {
			bar.update(uploadedMutiple * barMultiple);
			uploadedMutiple++;
			if (uploadedMutiple * barMultiple >= barLength - barMultiple)
				uploadedMutiple--;
		});
		ftpClient.put(uploadFileStream, ftpPath_, function (err) {
			if (err) {
				console.log('upload error');
				throw err;
			}
			ftpClient.end();
			sleep(1000);
			bar.update(barLength);
			//包上传成功后，发送http请求给服务器
			eventEmitter.emit('send_http');
		});
	});
}

//获取本机的ip
function getIPAdress() {
	var interfaces = os.networkInterfaces();
	for (var devName in interfaces) {
		var iface = interfaces[devName];
		for (var i = 0; i < iface.length; i++) {
			var alias = iface[i];
			if (alias.family === 'IPv4' && alias.address !== '127.0.0.1' && !alias.internal) {
				return alias.address;
			}
		}
	}
}

//将ini文件转json文件
function parseINIString(data) {
	var regex = {
		section: /^\s*\[\s*([^\]]*)\s*\]\s*$/,
		param: /^\s*([\w\.\-\_]+)\s*=\s*(.*?)\s*$/,
		comment: /^\s*;.*$/
	};
	var value = {};
	let values = [];
	var lines = data.split(/\r\n|\r|\n/);
	var section = null;
	let i = 0;
	for (; i < lines.length; i++) {
		let line = lines[i];
		if (regex.comment.test(line)) {
			return;
		} else if (regex.param.test(line)) {
			var match = line.match(regex.param);
			if (section) {
				value[match[1]] = match[2];
			}
			if (i == lines.length - 1) {
				values.push(value);
			}
		} else if (regex.section.test(line)) {
			var match = line.match(regex.section);
			value['name'] = match[1];
			section = match[1];
		} else if (line.length == 0 && section) {
			values.push(value);
			section = null;
			value = {};
		}
	}
	return values;
}

//根据release和test的包名，得到相应的文件夹名
function getFolderName(fileName){
    let index = fileName.lastIndexOf("_");
    let folderName = fileName.substring(0,index);
    let firstIndex = folderName.indexOf("_");
    let lastIndex = folderName.lastIndexOf("_");
    folderName = folderName.substring(0,firstIndex) + folderName.substring(lastIndex);
    return folderName;
}

//创建用户的log上传到ftp上的文件夹
 function createUserLogsFolderOnFtp(userFolderName){
	let client = new Client();
	client.connect(ftpOptionLogs);
	client.on('error',function(msg){
		console.log('msg: ' + msg);
	});
	client.on('ready',function(){
		client.cwd(ftpPath,function(err,currentDir){
			if(err){
				console.error(err);
				throw err;
			}
			client.list(function(err,list){
				if(err){
					throw err;
				}
				let exist = false;
				for(let i = list.length - 1;i >= 0;--i){
					if(list[i].name == userFolderName){
						exist = true;
						break;
					}
				}
				if(!exist){
					client.mkdir(userFolderName,function(err){
						if(err){
							throw err;
						}
						client.end();
					});
				}else{
					client.end();
				}
			});
		});
	});
}

