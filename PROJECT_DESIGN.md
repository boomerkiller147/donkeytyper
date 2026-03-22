# DonkeyTyper PROJECT_DESIGN

## 1. 项目定位

DonkeyTyper 现在是一个以结构化文档模型为中心的桌面编辑器。

- 编辑主事实是 `Document -> Paragraph -> InlineRun` 模型，不是 `QTextDocument`
- Qt 编辑器负责输入与显示
- `EditorController` 负责模型修改、事务、撤销重做和段落语义
- Markdown 预览与 Markdown 导出都从同一份控制器文档生成
- paragraph type 系统负责段落语义、渲染参数、命令入口和导出规则

系统现在回答的是“当前文档模型如何被编辑、渲染、导出和持久化”，不是“未来准备演化成什么”。

## 2. 核心模型

### 2.1 Document

owner: `model/document.py`

输入:
- `.dty` 载入结果
- 纯文本导入结果
- controller 事务修改结果

输出:
- 当前完整文档状态
- `to_dict()` 持久化载荷
- Markdown 导出与预览的源数据

`Document` 由 `Paragraph` 列表组成。它保证空文档时至少存在一个段落，并提供 `from_dict()`、`from_plain_text()`、`to_dict()`。

### 2.2 Paragraph

owner: `model/paragraph.py`

输入:
- `runs`
- `tag`
- `tag_data`
- `default_font_size`
- `alignment`

输出:
- 规范化后的段落语义
- 段落纯文本
- 段落级 display style

`Paragraph` 现在持有这几个核心事实：

- `tag` 是段落语义标签
- `tag_data` 是段落级附加语义，当前承载 `pending` 和 `display_style`
- `default_font_size` 是普通文本段落的段落级字号事实
- `alignment` 是段落对齐事实
- `runs` 是字符级 rich text truth

`Paragraph.normalize()` 会根据当前 registry 规则收口段落状态：

- 有文本且 `tag=empty` 时，按 `default_font_size` 提升为对应文本 tag
- 没有文本时，普通文本 tag 会回落为 `empty`
- 不允许空状态持久化的特殊段落，在不是 `pending` 的情况下也会回落为 `empty`

### 2.3 InlineRun

owner: `model/inline_run.py`

输入:
- 文本和字符级样式字段

输出:
- 持久化 run 数据
- 渲染层字符样式输入

`InlineRun` 保存字符级样式事实：

- `text`
- `font_size`
- `font_family`
- `bold`
- `italic`
- `color`
- `alpha`
- `underline`

当前架构里，段落级持续覆盖和字符级样式是分开的：

- 段落持续显示规则来自 paragraph type + `tag_data.display_style`
- 字符级 rich text truth 保存在 runs

## 3. Paragraph Type 系统

### 3.1 系统定位

owner: `paragraphs/`

输入:
- 内建 paragraph type 定义
- 用户 JSON 定义
- `.dty` 文件内嵌定义

输出:
- 运行时 paragraph registry
- 段落 tag 语义解释
- 命令入口、装饰规则、导出规则、布局规则

Paragraph type 系统现在不再是一个散落在旧 helper 里的概念集合，而是统一收口在 `paragraphs.types`、`paragraphs.builtins`、`paragraphs.config`、`paragraphs.registry`。

### 3.2 ParagraphTypeSpec

owner: `paragraphs/types.py`

`ParagraphTypeSpec` 是当前段落语义的唯一结构化定义。当前字段为：

- `tag`
- `display_name`
- `content_kind`
- `render_kind`
- `uses_runs`
- `allows_text_input`
- `contagious`
- `allows_empty_persistence`
- `layout`
- `text_style`
- `decoration`
- `commands`
- `export`

嵌套结构当前字段为：

- `layout`
  - `rendered_font_size`
  - `line_height`
  - `top_margin`
  - `bottom_margin`
  - `left_margin`
  - `text_indent`
  - `prefixed_item_gap`
  - `prefix_gap`
  - `ordered_prefix_min_digits`
  - `expand_text_start`
- `text_style`
  - `color`
  - `bold`
  - `italic`
  - `font_family`
- `decoration`
  - `prefix_kind`
  - `prefix_text`
  - `suffix_kind`
  - `has_border`
  - `has_background`
  - `custom_renderer`
- `commands`
  - `create_command`
  - `create_from_tag`
  - `clean_command`
  - `clean_to_tag`
- `export`
  - `markdown_role`
  - `markdown_prefix`
  - `markdown_suffix`

### 3.3 当前内建类型

owner: `paragraphs/builtins.py`

系统当前内建的核心类型包括：

- `empty`
- `body`
- `body_small`
- `heading_1` 到 `heading_5`
- `ordered_item`
- `unordered_item`
- `image`
- `canvas`

其中：

- 普通文本段落依赖 `default_font_size -> text tag` 映射
- 列表段落使用 `render_kind=decorated_text` 和 `decoration.prefix_kind`
- `image` / `canvas` 是 block 类型，占位了自定义块渲染语义，但不是 JSON 扩展入口

### 3.4 当前语义边界

paragraph type 当前负责：

- 段落可否输入文本
- 段落是否 contagious
- 段落空状态能否稳定存在
- 段落显示布局
- 段落装饰前缀
- create / clean 命令映射
- Markdown 导出角色和导出 affix

paragraph type 当前不负责：

- 直接驱动 Qt UI 控件
- 自带 Python 扩展逻辑
- 注入新的 Qt block renderer
- 绕过 controller 直接修改文档

## 4. Registry 与扩展机制

### 4.1 唯一入口

owner: `paragraphs/registry.py`

输入:
- `ParagraphTypeSpec`
- 用户 definition payload
- `.dty` definition payload

输出:
- 运行时注册表
- create / clean 命令索引
- prefix / export / font-size / markdown helper

registry 是当前唯一入口。所有 paragraph type 定义最终都进入 `configure_runtime_paragraph_type_registry(...)` 和 `apply_paragraph_type_definitions(...)`，再由其他系统读取。

JSON 不直接驱动 UI，也不直接驱动 controller。它先进入 registry，系统其他层只读 registry。

### 4.2 三类来源

当前运行时 registry 有三类定义来源：

1. builtin
2. user JSON：`paragraph_types/paragraph_types.json`
3. 文件内嵌：`.dty` 的 `paragraph_type_definitions`

### 4.3 注册顺序与覆盖规则

owner: `WindowSessionCoordinator.rebuild_runtime_paragraph_type_registry()`

顺序固定为：

1. `reset_runtime_paragraph_type_registry()` 载入 builtin
2. 应用 user definitions，`allow_builtin_override=False`
3. 应用 document definitions，`allow_builtin_override=True`

因此当前覆盖规则是：

- builtin 永远先注册
- user JSON 不能覆盖 builtin tag
- `.dty` 内嵌定义可以覆盖同名 user tag，也可以覆盖 builtin tag
- 同一来源内部重复 tag，后者会被跳过
- 非法 definition 会被跳过并记录 warning，不会让 registry 整体失效

### 4.4 Registry 当前提供的语义查询

registry 当前已经成为这些系统的共享语义来源：

- `get_paragraph_type_spec()`
- `find_tag_for_create_command()`
- `find_clean_transition_tag()`
- `list_registered_create_commands()`
- `list_registered_clean_commands()`
- `get_markdown_role()`
- `get_markdown_prefix()`
- `get_markdown_suffix()`
- `get_plain_display_prefix_text()`
- `get_default_paragraph_font_size()`
- `get_text_tag_for_font_size()`

这意味着当前系统不存在“多入口注册”或“各处自己维护一套段落语义”的设计。

### 4.5 JSON 配置能力

owner: `paragraphs/config.py` + `paragraphs/registry.py`

输入:
- 仓库根目录 `paragraph_types/paragraph_types.json`
- 可选环境变量 `DONKEYTYPER_PARAGRAPH_TYPES`

输出:
- 用户 paragraph type definition 列表

用户定义新段落的方式是编辑 `paragraph_types.json`，其顶层结构是：

```json
{
  "definitions": [
    {
      "tag": "note",
      "display_name": "Note",
      "render_kind": "decorated_text",
      "uses_runs": true,
      "allows_text_input": true,
      "contagious": false,
      "allows_empty_persistence": true,
      "layout": {
        "rendered_font_size": 18,
        "line_height": 26.0
      },
      "decoration": {
        "prefix_text": "※"
      },
      "commands": {
        "create_command": "/note/",
        "create_from_tag": "body",
        "clean_command": "/clean/",
        "clean_to_tag": "body"
      },
      "export": {
        "markdown_role": "paragraph",
        "markdown_prefix": "> ",
        "markdown_suffix": ""
      }
    }
  ]
}
```

当前 JSON 能力是分离式的：

- `commands` 定义命令入口
- `decoration` 定义编辑器显示前缀
- `export` 定义 Markdown 导出 affix

当前实现里，`decoration.prefix_text="※"` 不会自动决定 Markdown 导出；导出是否为 `> ` 由 `export.markdown_prefix` / `markdown_suffix` 单独决定。

### 4.6 不允许的扩展

当前 paragraph type JSON 不支持：

- 自定义 Python 行为
- 自定义 Qt renderer 注入
- 自定义 controller 命令实现
- 直接声明新的 block widget 或新的视图层 owner

现在可扩展的是数据定义，不是代码注入。

## 5. 编辑架构

### 5.1 controller

owner: `editor/controller.py`

输入:
- bridge 同步过来的 caret / selection / document
- input coordinator 发起的编辑事务
- format coordinator 发起的样式事务

输出:
- 修改后的 `Document`
- 事务记录
- undo / redo 快照

`EditorController` 现在拥有：

- 文档模型修改
- caret / selection 模型状态
- 输入样式状态和 slot 状态
- 文档事务、合并事务、撤销重做
- 段落 split / merge / clean / contagious continuation
- internal paste / external copy 的模型语义处理

controller 不拥有：

- Qt toolbar 状态
- 预览视图状态
- 主窗口装配逻辑

### 5.2 WindowEditorBridge

owner: `app/window_editor_bridge.py`

输入:
- editor 当前光标和选区
- controller 当前文档、caret、selection

输出:
- editor -> controller 同步
- controller -> editor 恢复

editor ↔ controller 同步现在统一由 `window_editor_bridge` 负责，包括：

- caret sync
- selection sync
- `textChanged` backsync
- 事务后 editor 恢复

桥接链路现在是：

- editor 变化时，bridge 把 Qt 状态同步回 controller
- controller 事务完成后，bridge 驱动刷新、恢复选区、更新字数、触发 dirty

当前设计边界非常明确：

- UI 不直接改 controller 的 caret / selection
- preview 不直接操作 controller
- format 不直接重建 editor 文档
- input 不直接把 editor 文本当成最终事实

## 6. Window 架构

### 6.1 总体拆分

当前主窗口已经拆为：

- `app/main_window.py`
- `app/window_input_coordinator.py`
- `app/window_format_coordinator.py`
- `app/window_preview_coordinator.py`
- `app/window_session_coordinator.py`
- `app/window_editor_bridge.py`

### 6.2 main_window.py

owner: `app/main_window.py`

输入:
- Qt widget / layout / shortcut 装配需求

输出:
- window 对象和 coordinator 依赖注入

`main_window.py` 现在是装配层。它负责：

- 构造 controller、editor、preview widget 和 toolbar
- 创建 coordinators 与 bridge
- 连接 Qt signals 到各 owner
- 处理窗口级样式、缩放、内容列边距
- 启动后调用一次 session-owned registry rebuild

`main_window` 现在不再拥有业务逻辑，不再作为 UI state、preview、session、输入语义的 owner。

### 6.3 WindowInputCoordinator

owner: `app/window_input_coordinator.py`

输入:
- 键盘文本输入
- IME commit
- Enter / Backspace / Delete
- cut / paste / internal paste

输出:
- controller 文档事务
- 事务 metadata
- 事务后 bridge 恢复

它负责把 Qt 输入事件翻译成 controller 事务，但不自己定义段落语义。

### 6.4 WindowFormatCoordinator

owner: `app/window_format_coordinator.py`

输入:
- toolbar UI 状态
- 当前光标 / 选区
- controller 事务后状态

输出:
- controller input style
- selection style 事务
- editor currentCharFormat
- toolbar enabled / selected state

它是当前 format / UI state 的唯一 owner。

### 6.5 WindowPreviewCoordinator

owner: `app/window_preview_coordinator.py`

输入:
- controller 当前文档
- Tab 预览切换

输出:
- editor 视图刷新
- markdown preview 文本
- 预览模式 UI 开关

它拥有预览视图模式，但不拥有语义状态。

### 6.6 WindowSessionCoordinator

owner: `app/window_session_coordinator.py`

输入:
- 打开 / 保存动作
- 载入 payload
- controller 当前文档

输出:
- 运行时 registry rebuild
- session 应用
- dirty / clean / title 状态

它是当前 file / session 的唯一入口。

## 7. 渲染与预览

### 7.1 editor 渲染

owner: `bridge/render_to_qt.py` 与 `bridge/layout_policy.py`

输入:
- controller `Document`
- registry layout / decoration / text_style 规则

输出:
- QTextEdit 显示内容
- 块级 layout 与字符格式

editor 渲染遵循：

- paragraph tag 决定段落级显示规则
- `tag_data.display_style` 优先于 paragraph type 默认 text style
- runs 提供字符级 fallback

### 7.2 preview 渲染

owner: `window_preview_coordinator.py`

输入:
- controller 文档

输出:
- 只读 markdown 文本视图

preview 当前链路是：

`controller -> render_document_to_markdown(document) -> markdown_preview.setPlainText(...)`

preview 当前特性：

- 使用只读文本视图显示 Markdown 结果
- 每次刷新都直接从 controller 文档重算
- 不缓存语义状态
- 不反写模型

这意味着 preview 不是第二套文档系统，只是 controller 文档的派生视图。

### 7.3 command 高亮

owner: `window_preview_coordinator.py`

当前 command 高亮只作用于 editor 视图，是基于当前 registry 的 create / clean commands 加上固定命令 token 做额外选区着色。

## 8. 输入与样式系统

### 8.1 唯一 owner

owner: `window_format_coordinator.py`

当前 UI state 不在 `main_window`，而由 `window_format_coordinator` 持有和同步。

当前归它管理的状态包括：

- toolbar 当前 size / alpha / color / bold / italic
- active slot
- slot states
- editor `currentCharFormat`
- toolbar enabled / disabled state

### 8.2 controller 同步链

format coordinator 负责把 UI state 同步到 controller：

- `set_input_style(...)`
- `set_active_slot(...)`
- `set_slot_state(...)`

同时它也负责把 controller 事务后的结果重新投影到：

- toolbar 文本和值
- currentCharFormat
- 单段选区时的一次性样式对齐

### 8.3 样式修改路径

当前样式路径分两类：

- 输入样式路径：影响后续输入的 run 样式
- 已选内容事务路径：通过 controller 修改 selection 或 paragraph display style

其中：

- 整段且属于 display style 字段时，走 paragraph display truth 路径
- 其他 inline 样式修改走 runs 路径

## 9. 命令系统

### 9.1 总体结构

owner:
- registry：发现 create / clean 命令
- input coordinator：在 Enter 时调度命令
- controller：执行命令对应的文档修改

### 9.2 registry 驱动部分

registry 当前驱动：

- create command 注册与枚举
- clean command 注册与枚举
- `token -> tag` 的 create 映射
- `tag -> clean_to_tag` 的 clean 映射

这部分现在完全来自 paragraph type registry。

### 9.3 固定命令部分

当前仍有一部分命令不是 registry 扩展定义，而是内建在 input/controller 里：

- `/center/`
- `/line/`
- `/block/`
- `/size/` 与 `/size N/`
- `/alpha/` 与 `/alpha N/`

因此当前命令系统是“registry 驱动的段落命令 + 固定实现的编辑命令”的组合，不是纯数据驱动解释器。

### 9.4 Enter 执行顺序

当前 Enter 顺序是：

1. 如果 editor 有选区，先删选区，再断段
2. 否则由 controller 在当前段落尝试命令执行
3. 命令没有消费时，再进入普通断段 / contagious continuation

`window_input_coordinator` 负责触发事务，controller 负责最终语义执行。

## 10. 复制 / 剪贴板

### 10.1 internal clipboard

owner:
- `window_input_coordinator.build_internal_clipboard_payload()`
- `EditorController.export_selection_for_internal_clipboard()`

输入:
- controller 当前选区

输出:
- JSON bytes payload

当前 internal paste fragment 模型为：

- `version`
- `paragraphs`
  - `text`
  - `tag`
  - `tag_data`

这是一种段落级语义剪贴板，而不是 plain text。

### 10.2 internal paste 合并规则

owner: `EditorController.paste_internal_fragments_at_caret()`

当前规则是：

- 单 fragment 时，如果目标段落与 fragment `tag`、`tag_data`、段落字号语义一致，则直接内联合并
- 否则按段落片段重建并插入
- 多 fragment 粘贴时保持段落边界和段落语义

当前实现已经修复“同语义不拆段”的问题：同 tag、同 tag_data、同段落字号的单段 fragment 会直接并入当前段落，不额外拆出新段落。

### 10.3 external copy

owner: controller + input coordinator

external copy 当前输出两种派生结果：

- plain text
- HTML

外部复制前缀当前来自 registry 的 display prefix 规则：

- ordered prefix 编号
- unordered bullet
- `decoration.prefix_text`

## 11. 文件与 session

### 11.1 唯一入口

owner: `window_session_coordinator.py`

当前 session / file 的唯一入口是 `window_session_coordinator`。

它负责：

- open
- save
- payload -> session -> runtime apply
- registry rebuild
- dirty / title

### 11.2 打开流程

当前打开流程是：

1. `open_file()` 选路径
2. `load_document_session(...)` 解析 `.dty` 或纯文本
3. `apply_loaded_document_session(session)` 应用结果
4. session coordinator rebuild runtime registry
5. controller 接收 document
6. format coordinator 恢复 slot / ui state
7. preview coordinator 恢复 editor 视图并刷新 preview
8. title / dirty 更新

### 11.3 保存流程

当前保存流程是：

1. 取 controller 当前 `document.to_dict()`
2. 从 registry 导出当前运行时 paragraph type definitions
3. 带上 UI state、active slot、slot states
4. `build_dty_payload(...)`
5. `save_dty_payload(...)`

### 11.4 `.dty` session 载荷

当前 `.dty` session 载荷包含：

- `format_version`
- `document`
- `paragraph_type_definitions`
- `ui_state`
- `active_slot`
- `slot_states`

`.dty` 当前既持久化文档，也持久化该文档运行时依赖的 paragraph type 定义。

## 12. Markdown 导出与预览

### 12.1 共用渲染器

owner: `exporters/markdown.py`

preview 和 export 当前共用同一条 Markdown 渲染路径：

- `render_document_to_markdown(document)`

preview 只是把结果显示到只读文本视图，export 则直接返回字符串。

### 12.2 render 规则

当前段落导出优先级为：

1. 特殊空段落规则和 divider 规则
2. paragraph tag 对应的 Markdown role
3. `export.markdown_prefix` / `export.markdown_suffix` override
4. heading / ordered / unordered 默认导出规则
5. body 文本转义规则

其中关键点是：

- paragraph tag 先决定段落语义
- 如果 paragraph type 提供 `export.markdown_prefix` / `markdown_suffix`，它优先覆盖默认段落文本包装

### 12.3 preview 行为边界

preview 当前明确满足：

- 不缓存语义状态
- 不反写模型
- 不自己维护第二套 paragraph truth
- 每次刷新都从 controller 文档直接重算

## 13. 自动排版

owner:
- `bridge/layout_policy.py`
- `main_window._apply_content_column_layout()`
- `window_preview_coordinator.apply_markdown_preview_layout()`

当前自动排版包括：

- editor / preview 内容列左右 margin 计算
- paragraph type 驱动的块级 line height / margin / prefix gap
- preview 只读文本视图的统一行高布局

自动排版当前是显示层规则，不写回模型语义。

## 14. Undo/Redo

owner: `EditorController`

输入:
- 各 coordinator 发起的 document transaction

输出:
- undo / redo 快照恢复

当前撤销重做基于 `TransactionRecord`：

- `before`
- `after`
- `kind`
- `merge_key`
- `metadata`

当前特性：

- 文本输入和 IME commit 可按 `merge_key` 合并事务
- undo / redo 恢复 document、caret、selection 三类快照
- Qt 自带 `QTextDocument` undo/redo 被关闭，真实撤销系统只在 controller

controller 恢复后，由 `window_editor_bridge.apply_controller_transaction()` 统一把结果投影回 editor / preview / format / dirty。

## 15. 扩展能力与边界

当前系统允许扩展的主要是 paragraph type 数据定义：

- 新 tag
- 新 create / clean 命令入口
- 新 display prefix
- 新 Markdown 导出 affix
- 新段落布局和默认 text style

当前系统的硬边界是：

- registry 是唯一段落定义入口
- controller 是唯一文档修改 owner
- `window_editor_bridge` 是 editor/controller 同步唯一桥
- `window_format_coordinator` 是 UI state 唯一 owner
- `window_session_coordinator` 是 session / file 唯一入口
- `window_preview_coordinator` 只管理预览视图，不管理模型状态
- `main_window.py` 只做装配，不承载业务语义

因此，这个系统现在的工作方式是：

- paragraph semantics 进入 registry
- coordinators 只处理各自窗口域责任
- controller 统一修改模型
- bridge 统一同步 editor 与 controller
- preview / export 统一从 controller 文档派生 Markdown
