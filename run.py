import os
from app import create_app

# 默认使用开发环境配置
config_name = os.getenv('FLASK_CONFIG') or 'development'
app = create_app(config_name)

if __name__ == '__main__':
    app.run(debug=True, port=5001)
