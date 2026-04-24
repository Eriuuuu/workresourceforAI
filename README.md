0. 多版本python的使用
py -3.8 -m pip install ........
py -3.8 -m main.py

-------------------镜像源------------------
修改镜像源
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
查看镜像源
pip config list


清华大学	https://pypi.tuna.tsinghua.edu.cn/simple
阿里云	https://mirrors.aliyun.com/pypi/simple
豆瓣	https://pypi.douban.com/simple
中国科学技术大学	https://pypi.mirrors.ustc.edu.cn/simple
华为云	https://repo.huaweicloud.com/repository/pypi/simple


-----------pipeline仓库后端----------------

1. 创建虚拟环境
py -3.8 -m venv myproject_env
这会在当前目录下生成一个名为 myproject_env 的文件夹，其中包含 Python 3.11 的独立运行环境。

2. 激活虚拟环境
myproject_env\Scripts\activate.bat
激活成功后，终端提示符前面会显示 (myproject_env)，表示当前正在使用该虚拟环境。


3. 安装依赖
激活虚拟环境后，python 和 pip 都指向虚拟环境内的版本，此时可以安全地安装依赖。
pip install -r requirements.txt


4. 运行项目
python main.py
此时使用的 Python 解释器和依赖都是虚拟环境内的，不会影响全局环境。

5. 退出虚拟环境
deactivate


-----------workresourceforAI仓库后端----------------

1. 创建虚拟环境
py -3.13 -m venv venv

2. 激活虚拟环境
venv\Scripts\activate.bat
激活成功后，终端提示符前面会显示 (myproject_env)，表示当前正在使用该虚拟环境。


3. 安装依赖
激活虚拟环境后，python 和 pip 都指向虚拟环境内的版本，此时可以安全地安装依赖。
pip install -r requirements.txt


4. 运行项目
***后端
# 开发模式启动 (热重载)
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
# 生产模式启动
uvicorn app.main:app --host 0.0.0.0 --port 8000

启动后：
API 服务: http://localhost:8000
Swagger 文档: http://localhost:8000/docs
Prometheus 指标: http://localhost:8000/metrics

***前端：npm run dev  会自动热更新。


5. 退出虚拟环境
deactivate


-----------workresourceforAI仓库数据库 可视化管理----------------
图数据库
http://localhost:7474/browser/
清空数据库：
MATCH (n)
DETACH DELETE n
查询所有关系和节点
MATCH (n)-[r]->(m)
RETURN n, r, m

向量数据库
在 J:\workresourceforAI\backend  下激活虚拟环境 venv\Scripts\activate.bat
启动服务 chroma run --path ./chroma_db --port 8888
使用第三方可视化软件 Vector DBZ 连接






