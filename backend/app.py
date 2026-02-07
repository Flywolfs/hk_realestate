"""
Flask API服务
提供租售比地图可视化所需的RESTful API
"""
from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS
import os
import sys

# 添加父目录到路径,以便导入data_loader
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils.data_loader import DataLoader

app = Flask(__name__, static_folder='../frontend/dist', static_url_path='')
CORS(app)  # 允许跨域访问

# 初始化数据加载器
BASE_PATH = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
data_loader = DataLoader(BASE_PATH)


@app.route('/api/estates', methods=['GET'])
def get_all_estates():
    """
    获取所有有坐标的小区列表
    返回基本信息用于地图标记
    """
    try:
        estates = data_loader.get_integrated_estates()
        return jsonify({
            'success': True,
            'count': len(estates),
            'data': estates
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/estates/<estate_id>', methods=['GET'])
def get_estate_detail(estate_id):
    """
    获取特定小区的详细信息
    """
    try:
        detail = data_loader.get_estate_detail(estate_id)
        if detail:
            return jsonify({
                'success': True,
                'data': detail
            })
        else:
            return jsonify({
                'success': False,
                'error': f'未找到ID为 {estate_id} 的小区'
            }), 404
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/rent-ratios', methods=['GET'])
def get_rent_ratios():
    """
    获取租售比统计信息
    包含最小值、最大值、平均值,用于前端色彩映射
    """
    try:
        stats = data_loader.get_rent_ratio_statistics()
        return jsonify({
            'success': True,
            'data': stats
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/api/search', methods=['GET'])
def search_estates():
    """
    按小区名称模糊搜索
    查询参数: keyword
    """
    try:
        keyword = request.args.get('keyword', '')
        if not keyword:
            return jsonify({
                'success': False,
                'error': '请提供搜索关键词'
            }), 400
        
        results = data_loader.search_estates_by_name(keyword)
        return jsonify({
            'success': True,
            'count': len(results),
            'data': results
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve_frontend(path):
    """
    服务前端静态文件
    """
    dist_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../frontend/dist')
    
    # 检查dist目录是否存在
    if not os.path.exists(dist_dir):
        return jsonify({
            'message': 'Frontend not built yet. Please run: cd frontend && npm install && npm run build'
        }), 404
    
    if path and os.path.exists(os.path.join(dist_dir, path)):
        return send_from_directory(dist_dir, path)
    else:
        return send_from_directory(dist_dir, 'index.html')


@app.errorhandler(404)
def not_found(e):
    """处理404错误"""
    return jsonify({
        'success': False,
        'error': '资源未找到'
    }), 404


@app.errorhandler(500)
def internal_error(e):
    """处理500错误"""
    return jsonify({
        'success': False,
        'error': '服务器内部错误'
    }), 500


if __name__ == '__main__':
    print("=" * 60)
    print("香港小区租售比地图可视化系统 - Flask API服务")
    print("=" * 60)
    print(f"数据源路径: {BASE_PATH}")
    print(f"API服务运行在: http://localhost:5000")
    print(f"API端点:")
    print(f"  - GET /api/estates")
    print(f"  - GET /api/estates/<id>")
    print(f"  - GET /api/rent-ratios")
    print(f"  - GET /api/search?keyword=<关键词>")
    print("=" * 60)
    
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)
