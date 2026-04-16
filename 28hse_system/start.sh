#!/bin/bash

# 香港小区租售比地图可视化系统 - 启动脚本

echo "=========================================="
echo "香港小区租售比地图可视化系统"
echo "=========================================="
echo ""

# 检查是否在正确的目录
if [ ! -d "backend" ] || [ ! -d "frontend" ]; then
    echo "错误: 请在项目根目录运行此脚本"
    exit 1
fi

# 检查Python依赖
echo "检查Python依赖..."
if ! command -v python3 &> /dev/null; then
    echo "错误: 未找到Python3,请先安装Python3"
    exit 1
fi

# 安装后端依赖
echo "安装后端依赖..."
cd backend
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt -q

# 启动Flask后端
echo ""
echo "启动Flask后端服务..."
python app.py &
BACKEND_PID=$!

cd ..

# 等待后端启动
sleep 3

echo ""
echo "=========================================="
echo "系统启动成功!"
echo "=========================================="
echo ""
echo "访问地址:"
echo "  开发模式(前端): http://localhost:3000"
echo "  生产模式(Flask): http://localhost:5000"
echo ""
echo "API端点:"
echo "  GET /api/estates - 获取所有小区"
echo "  GET /api/estates/<id> - 获取小区详情"
echo "  GET /api/rent-ratios - 获取租售比统计"
echo "  GET /api/search?keyword=<关键词> - 搜索小区"
echo ""
echo "按Ctrl+C停止服务"
echo "=========================================="

# 等待用户停止
wait $BACKEND_PID
