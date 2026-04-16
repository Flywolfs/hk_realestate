# 安全防护指南

## 日志分析结果

你遇到的是典型的**自动化网络扫描攻击**:

### 攻击来源
- **45.153.34.68**: 尝试HTTP GET/POST探测
- **18.218.118.203** (AWS IP): 多种协议探测
  - TLS/SSL握手探测 (`\x16\x03\x01`)
  - SSH协议探测 (`SSH-2.0-Go`)
  - 正常HTTP请求混合

### 攻击目的
- 端口扫描,寻找开放服务
- 协议识别,判断服务类型
- 漏洞探测,寻找可利用的安全漏洞

---

## 已实施的安全措施

### 1. **IP请求频率限制**
```
限制: 60次请求/分钟
封禁时长: 10分钟
```
- 防止DDoS攻击和暴力破解
- 超过限制的IP会被临时封禁
- 返回HTTP 429状态码

### 2. **可疑请求检测**
自动识别以下攻击模式:
- TLS/SSL协议探测
- SSH协议探测
- XSS跨站脚本攻击
- 路径遍历攻击 (`../`)
- SQL注入攻击 (`SELECT`, `UNION`)

### 3. **完整日志记录**
- 所有请求记录到 `access.log`
- 包含:IP、请求方法、路径、User-Agent
- 可疑请求特别标记为 `SUSPICIOUS REQUEST`

---

## 建议的额外措施

### 1. **生产环境部署**
```bash
# 使用Gunicorn代替Flask内置服务器
pip install gunicorn

# 启动命令
gunicorn -w 4 -b 0.0.0.0:5000 app:app
```

### 2. **使用Nginx反向代理**
```nginx
server {
    listen 80;
    server_name your-domain.com;

    # 限制请求体大小
    client_max_body_size 1M;

    # 隐藏服务器版本
    server_tokens off;

    # IP白名单(可选)
    # allow 192.168.1.0/24;
    # deny all;

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header Host $host;
    }

    # 限制请求频率
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20;
}
```

### 3. **防火墙配置**
```bash
# 使用ufw限制访问
sudo ufw allow 22/tcp          # SSH
sudo ufw allow 80/tcp          # HTTP
sudo ufw allow 443/tcp         # HTTPS
sudo ufw enable

# 封禁已知恶意IP
sudo ufw deny from 45.153.34.68
sudo ufw deny from 18.218.118.203
```

### 4. **使用Fail2ban自动封禁**
```bash
# 安装fail2ban
sudo apt-get install fail2ban

# 配置文件 /etc/fail2ban/jail.local
[flask-app]
enabled = true
filter = flask-app
logpath = /path/to/backend/access.log
maxretry = 10
bantime = 3600
findtime = 600
```

### 5. **HTTPS加密**
```bash
# 使用Let's Encrypt免费证书
sudo apt-get install certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

### 6. **隐藏错误信息**
在生产环境中修改启动配置:
```python
# app.py 最后一行改为
app.run(host='0.0.0.0', port=5000, debug=False)
```

### 7. **定期监控日志**
```bash
# 查看可疑请求
grep "SUSPICIOUS" access.log

# 统计访问最多的IP
awk '{print $1}' access.log | sort | uniq -c | sort -rn | head -10

# 实时监控
tail -f access.log | grep "SUSPICIOUS"
```

---

## 如何处理当前攻击

### 立即措施:
1. ✅ **已实施** - 代码已添加频率限制和日志记录
2. 重启Flask服务使新配置生效
3. 监控 `access.log` 查看后续攻击

### 短期措施:
1. 封禁已知恶意IP (使用防火墙)
2. 如果是测试环境,考虑不对公网开放
3. 配置Nginx反向代理

### 长期措施:
1. 使用CDN服务 (Cloudflare免费版)
2. 部署WAF (Web Application Firewall)
3. 定期更新依赖包
4. 进行安全审计

---

## 常见问题

**Q: 这些攻击会造成什么危害?**
A: 目前的探测行为本身危害不大,但如果发现漏洞可能会:
- 窃取数据
- 植入恶意代码
- 消耗服务器资源

**Q: 为什么会被扫描?**
A: 互联网上存在大量自动化扫描程序,会扫描所有公网IP的所有端口。只要服务对公网开放,就会被扫描。

**Q: 如何知道是否被攻破?**
A: 检查以下迹象:
- 异常的CPU/内存使用
- 未知的进程
- 数据被篡改
- 异常的网络流量

**Q: 测试环境需要这么多防护吗?**
A: 如果仅本地测试,可以:
```python
# 只监听localhost
app.run(host='127.0.0.1', port=5000, debug=True)
```

---

## 联系与反馈

如发现安全问题,请立即:
1. 检查日志文件 `access.log`
2. 记录可疑IP和请求模式
3. 考虑暂时关闭服务

## 更新记录
- 2026-03-01: 初始版本,添加基础安全防护
