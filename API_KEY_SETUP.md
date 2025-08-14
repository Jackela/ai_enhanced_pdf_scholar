# API 密钥配置指南

AI Enhanced PDF Scholar 支持多种方式配置 Google Gemini API 密钥：

## 🔑 获取 API 密钥

1. 访问 [Google AI Studio](https://makersuite.google.com/app/apikey)
2. 创建新的 API 密钥
3. 复制密钥（格式：`AIzaSy...`）

## ⚙️ 配置方式（按优先级）

### 方式 1：环境变量（推荐）
```bash
# Windows (PowerShell)
$env:GEMINI_API_KEY="你的API密钥"

# Windows (CMD)
set GEMINI_API_KEY=你的API密钥

# Linux/Mac
export GEMINI_API_KEY=你的API密钥
```

### 方式 2：.env 文件
创建 `.env` 文件在项目根目录：
```env
GEMINI_API_KEY=你的API密钥
```

### 方式 3：应用内设置
1. 启动应用
2. 点击 "Settings" 按钮
3. 输入 API 密钥
4. 点击保存

### 方式 4：命令行参数
```bash
python main.py --api-key 你的API密钥
```

## 🔒 安全提醒

- ⚠️ **切勿将API密钥提交到Git仓库**
- `.env` 文件已在 `.gitignore` 中排除
- 使用环境变量是最安全的方式

## 🧪 测试配置

```bash
# 测试API密钥是否正确配置
python -c "from config import Config; print('API Key:', 'OK' if Config.get_gemini_api_key() else 'NOT FOUND')"
```

## 🚀 启动应用

配置完API密钥后：
```bash
python main.py
```

应用将自动检测并使用配置的API密钥。