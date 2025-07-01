# AI Enhanced PDF Scholar

[![Python](https://img.shields.io/badge/python-3.8%2B-blue)](https://python.org)
[![PyQt6](https://img.shields.io/badge/PyQt6-6.0%2B-green)](https://www.riverbankcomputing.com/software/pyqt/)
[![License](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Tests](https://img.shields.io/badge/tests-212%20passing-brightgreen)](tests/)

🚀 **一个基于PyQt6的AI增强PDF学术阅读工具，通过智能对话让学术阅读更高效**

## ⚠️ 免责申明

**这是一个纯粹的 Vibe Coding 项目！** 🎨

- 本项目是出于兴趣和学习目的开发的实验性工具
- 目前**只支持 Google Gemini API**（后续开发计划会支持其他AI服务，但目前还没做）
- 代码质量和功能完整性可能存在局限性
- 使用本工具产生的任何结果请自行判断准确性
- 不对使用本工具造成的任何损失或问题承担责任

## ✨ 主要特性

### 🤖 AI智能对话
- **一键AI问答**：选择PDF中的任意文本，向AI提问获得智能解释
- **上下文理解**：AI能理解全文语境，提供准确的回答
- **Markdown渲染**：AI回答支持完整的Markdown格式，包括代码高亮、列表、表格等

### 🎨 现代化界面
- **Material Design**：采用现代化设计语言，8种精美配色方案
- **完全响应式**：智能适配不同屏幕尺寸（平板到4K显示器）
- **零硬编码**：所有UI参数可配置，支持个性化定制
- **流畅动画**：250ms平滑过渡，提供优雅的用户体验

### 📖 强大的PDF处理
- **高质量渲染**：150 DPI高清PDF显示
- **智能选择**：支持文本选择和区域截图两种模式
- **多页面支持**：流畅的页面导航和缩放功能

### 🔧 技术优势
- **异步处理**：多线程架构，UI永不卡顿
- **错误恢复**：完善的错误处理和恢复机制
- **高测试覆盖**：212个测试用例，保证代码质量
- **跨平台兼容**：支持Windows、macOS、Linux

## 🚀 快速开始

### 环境要求
- Python 3.12+
- PyQt6 6.9.1+
- 支持的操作系统：Windows 10+, macOS 10.15+, Linux

### 安装步骤

1. **克隆项目**
```bash
git clone https://github.com/yourusername/ai_enhanced_pdf_scholar.git
cd ai_enhanced_pdf_scholar
```

2. **安装依赖**
```bash
pip install -r requirements.txt
```

3. **配置AI服务**
   - 获取 [Google Gemini API Key](https://makersuite.google.com/app/apikey)
   - 启动应用后点击"⚙️ Settings"配置API密钥

4. **启动应用**
```bash
python main.py
```

## 📱 使用方法

### 基本操作
1. **打开PDF**：点击"📂 Open PDF"按钮选择PDF文件
2. **选择文本**：在PDF中用鼠标选择想要询问的文本
3. **AI问答**：在弹出的对话框中输入问题或直接点击提交
4. **查看回答**：AI的回答将显示在右侧面板，支持Markdown格式

### 高级功能
- **模式切换**：在工具栏切换文本选择/区域截图模式
- **响应式布局**：拖拽窗口边缘调整界面大小，UI自动适配
- **批量标注**：可同时创建多个标注，便于对比学习

## 🛠️ 技术栈

### 核心技术
- **UI框架**：PyQt6 - 现代化跨平台GUI框架
- **PDF处理**：PyMuPDF - 高性能PDF渲染引擎
- **AI服务**：Google Gemini - 先进的大语言模型
- **Markdown**：Python-Markdown - 富文本渲染支持

### 架构设计
- **MVC模式**：清晰的模型-视图-控制器架构
- **信号槽机制**：基于事件驱动的组件通信
- **响应式设计**：断点式布局适配系统
- **模块化开发**：高内聚低耦合的组件设计

## 🧪 开发与测试

### 运行测试
```bash
# 运行所有测试
python -m pytest tests/ -v

# 运行特定测试
python -m pytest tests/test_modern_ui_features.py -v

# 生成测试覆盖报告
python -m pytest tests/ --cov=src --cov-report=html
```

### 测试统计
- **总测试数量**：212个
- **测试分类**：单元测试、组件测试、集成测试、UI测试、错误场景测试
- **覆盖率**：核心功能100%覆盖
- **测试框架**：pytest + pytest-qt (GUI测试)

## 📂 项目结构

```
ai_enhanced_pdf_scholar/
├── 📄 main.py                    # 主应用程序入口
├── ⚙️ config.py                  # 响应式配置系统
├── 📋 requirements.txt           # 项目依赖
├── 📖 README.md                  # 项目说明（中文）
├── 📖 README_EN.md               # 项目说明（英文）
├── 📚 PROJECT_DOCS.md            # 技术文档
├── 📁 src/                       # 核心源代码
│   ├── 🖼️ pdf_viewer.py          # PDF渲染和交互
│   ├── 🤖 llm_service.py         # AI服务接口
│   ├── 💬 annotation.py          # 智能标注组件
│   ├── 📱 responsive_utils.py    # 响应式UI工具
│   └── 🔧 ...                    # 其他核心模块
└── 🧪 tests/                     # 测试套件 (212个测试)
    ├── 🔬 test_*.py              # 各种测试文件
    └── ⚙️ conftest.py            # 测试配置
```

## 🤝 贡献指南

我们欢迎各种形式的贡献！

### 贡献方式
1. **报告问题**：发现bug请创建Issue
2. **功能建议**：有新想法请创建Feature Request
3. **代码贡献**：Fork项目并提交Pull Request
4. **文档改进**：帮助完善项目文档

### 开发环境
```bash
# 克隆开发分支
git clone -b develop https://github.com/yourusername/ai_enhanced_pdf_scholar.git

# 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 安装开发依赖
pip install -r requirements.txt
pip install pytest pytest-qt pytest-cov

# 运行测试确保环境正常
python -m pytest tests/ -v
```

## 📝 更新日志

### Version 2.0.0 (2025-07-02) - 响应式UI重构
- ✅ **完全响应式设计**：消除所有硬编码，支持4个断点适配
- ✅ **Markdown渲染支持**：AI回答支持富文本格式
- ✅ **Material Design界面**：现代化视觉设计
- ✅ **智能窗口管理**：自动居中和尺寸适配
- ✅ **测试覆盖增强**：新增22个UI测试，总数达212个

### Version 1.0.0 (2025-01-15) - 初始版本
- 🎉 **基础功能完成**：PDF阅读、AI问答、智能标注
- 🎉 **PyQt6界面**：现代化桌面应用
- 🎉 **Gemini集成**：AI大语言模型支持
- 🎉 **跨平台支持**：Windows、macOS、Linux兼容

## 📄 许可证

本项目采用 [MIT License](LICENSE) 开源许可证。

## 🙏 致谢

感谢以下开源项目的支持：
- [PyQt6](https://www.riverbankcomputing.com/software/pyqt/) - 强大的GUI框架
- [PyMuPDF](https://pymupdf.readthedocs.io/) - 优秀的PDF处理库
- [Google Gemini](https://deepmind.google/technologies/gemini/) - 先进的AI技术
- [Python-Markdown](https://python-markdown.github.io/) - Markdown渲染引擎

---

<div align="center">

**如果这个项目对您有帮助，请给我们一个 ⭐ Star！**

[报告问题](../../issues) • [功能建议](../../issues/new) • [贡献代码](../../pulls)

</div>
