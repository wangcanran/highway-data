# 高速公路数据API服务

一个基于Flask的高速公路收费系统数据API服务，集成**GPT-4智能Agent**，支持自然语言查询。

## ✨ 特性

- 🤖 **GPT-4智能Agent**: 使用大语言模型理解自然语言需求，智能推荐合适的API
- 📊 **完整数据**: 提供路段、收费站、门架、交易记录等完整数据访问
- 📈 **统计分析**: 内置流量统计、收费分析、车型分布等分析功能
- 🎨 **美观界面**: 现代化Web界面，交互友好
- 📖 **详细文档**: 完整的API使用指南和示例代码
- 🌐 **跨域支持**: 启用CORS，支持跨域调用

## 🚀 快速开始

### 1. 安装依赖

```bash
cd highway_api
pip install -r requirements.txt
```

### 2. 配置数据库

在 `app.py` 中修改数据库路径（如果需要）：

```python
DB_PATH = r'D:\python_code\testwork\highway_db_20251120_163848.sqlite'
```

### 3. 启动服务

```bash
python app.py
```

服务将在 `http://localhost:5000` 启动。

### 4. 访问Web界面

在浏览器中打开：`http://localhost:5000`

## 📚 API文档

详细的API使用指南请查看：[API_GUIDE.md](API_GUIDE.md)

### 快速示例

#### 使用智能Agent

```bash
curl -X POST http://localhost:5000/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{"query": "查询2023年1月的交易记录"}'
```

#### 获取路段信息

```bash
curl http://localhost:5000/api/sections
```

#### 获取交易记录

```bash
curl "http://localhost:5000/api/transactions/entrance?section_id=G5615530120&limit=10"
```

#### 统计分析

```bash
curl "http://localhost:5000/api/statistics/traffic-flow?start_date=2023-01-01&end_date=2023-01-31"
```

## 📦 项目结构

```
highway_api/
├── app.py                 # Flask应用主文件
├── agent.py              # 智能Agent实现
├── requirements.txt      # 项目依赖
├── README.md            # 项目说明
├── API_GUIDE.md         # API使用指南
└── templates/
    └── index.html       # Web界面
```

## 🎯 主要功能

### 1. GPT-4智能Agent（两步流程）

**第一步：需求理解**
- 使用GPT-4理解用户的自然语言描述
- 识别用户的应用场景（如：路径规划、交通分析、收费报表等）
- 分析所需的数据类型

**第二步：API匹配**
- 根据需求分析结果，匹配对应的API接口
- 提供详细的调用示例和参数说明
- 展示响应数据格式

**特点：**
- ✅ 真正的语义理解，不只是关键词匹配
- ✅ 支持复杂场景描述（如："我需要做路径规划"）
- ✅ LLM失败时自动回退到规则匹配
- ✅ 可处理各种表达方式

### 2. 数据API

#### 路段信息
- `GET /api/sections` - 获取所有路段
- `GET /api/sections/{section_id}` - 获取指定路段

#### 收费站信息
- `GET /api/toll-stations` - 获取收费站列表
- `GET /api/toll-stations/{station_id}` - 获取指定收费站

#### 门架信息
- `GET /api/gantries` - 获取门架列表
- `GET /api/gantries/{gantry_id}` - 获取指定门架

#### 交易记录
- `GET /api/transactions/entrance` - 入口交易记录
- `GET /api/transactions/exit` - 出口交易记录
- `GET /api/transactions/gantry` - 门架交易记录

#### 统计分析
- `GET /api/statistics/traffic-flow` - 交通流量统计
- `GET /api/statistics/revenue` - 收费统计
- `GET /api/statistics/vehicle-distribution` - 车型分布

### 3. Web界面

- 智能Agent交互界面
- API文档在线查看
- 示例代码和参数说明
- 响应数据预览

## 💡 使用场景

1. **数据查询**: 快速查询高速公路运营数据
2. **报表生成**: 自动化生成各类统计报表
3. **数据分析**: 为数据分析和可视化提供数据源
4. **系统集成**: 与其他系统进行数据对接
5. **开发测试**: 为前端开发提供模拟数据接口

## 🔧 技术栈

- **后端**: Flask 3.0
- **数据库**: SQLite
- **前端**: HTML5 + TailwindCSS + JavaScript
- **AI**: GPT-4 (OpenAI API) + 规则回退机制
- **LLM配置**: 
  - Model: gpt-4.1-2025-04-14
  - Base URL: https://4zapi.com/v1
  - Timeout: 120s

## 📝 API响应格式

### 成功响应
```json
{
  "success": true,
  "data": [...],
  "count": 10
}
```

### 错误响应
```json
{
  "success": false,
  "error": "错误信息"
}
```

## 🌟 使用建议

1. **分页查询**: 交易记录数据量较大，建议使用分页参数
2. **日期格式**: 使用 `YYYY-MM-DD` 或 `YYYY-MM-DD HH:MM:SS` 格式
3. **首次使用**: 先调用 `/api/sections` 了解可用路段
4. **统计分析**: 适合用于报表生成和数据可视化
5. **Agent优先**: 不确定用哪个API时，优先使用Agent

## 📄 许可证

MIT License

## 🤝 贡献

欢迎提交问题和改进建议！

---

**版本**: v1.0  
**创建日期**: 2024-11-20
