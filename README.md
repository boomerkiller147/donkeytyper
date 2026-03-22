
# DonkeyTyper

DonkeyTyper 是一个基于 `PySide6` 的桌面编辑器，当前仓库已经包含可运行的应用代码

## 环境要求

- Python 3.10 或更高版本
- 可用的桌面图形环境
- `pip`

## 运行依赖

当前仓库对外部环境的最小要求是：

- `PySide6`

## 安装依赖

```bash
python -m pip install -r requirements.txt
```

当前最小依赖包括：

- `PySide6`


## 启动项目

在仓库根目录执行：

```bash
python DonkeyTyper/DonkeyTyper.py
```


# 关于donkeytyper

donkeytyper是一个基于段落语义的富文本编辑器



DonkeyTyper 的目标是让文本编辑回归一种更自然的方式：

在输入时，你不需要关心样式、格式或排版细节，  
只需要确定两件事：

- 你写下了哪些文字
- 这段内容属于什么类型（例如正文、列表、提示等）

编辑器会根据这些语义信息，自动完成显示和结构组织。

---

在内部，DonkeyTyper 使用一种“语句 + tag”的数据结构：

每一段文本都带有明确的语义标签（tag），  
这些标签不是视觉样式，而是内容结构的一部分。

这种结构带来的好处是：

- 编辑过程更简单（无需手动调整格式）
- 文档结构天然清晰
- 可以简单的对全文进行同一排版
- 同一份内容可以被稳定且轻松地转换为不同形式：

  - Markdown
  - 富文本
  - 结构化文档
  - 或其他自定义格式

## 段落类型的使用方式

DonkeyTyper 提供两种方式来指定一段内容的类型：

1️.通过界面操作

你可以通过调整字号大小来决定标题层级，例如：

18pt--32pt→ 六级标题
14pt-16pt → 大小两种正文

2️.通过命令输入

在空段落中输入指令可以快速切换段落类型：

/ord/ → 有序列表
/unord/ → 无序列表
/clean/ → 恢复为普通段落（输入后回车生效）

donkeytyper采用统一注册的方式来注册特殊段落，你可以试着修改paragrap_json文件来创建属于自己的特殊段落，自定义渲染模式和行为模式。

## 未来计划

现在项目的完成度还仅在概念展示的阶段，后续预期推进的功能有：

0.对内容的整理
1.特殊段编辑GUI
2.对图片，视频，画板等更多内容的支持
3.更多的导出格式
4.对几种常见写作情况的样式配列表（论文，报告，笔记，小说）等_

如果现在就想用用看，下面有关于如何配置自定义段落的说明



# 自定义段落类型

`paragraph_types.json` 是 DonkeyTyper 的用户可编辑段落类型注册表。

它的作用是让你不用修改源码，就可以定义自己的段落类型，包括：

- 如何输入这个段落类型
- 它在编辑器里如何显示
- 它复制为普通文本时如何带前标
- 它导出为 Markdown 时是什么格式

如果你只想直接开始，请先看“快速开始”和 `note` 示例。

## 快速开始

1. 打开 [paragraph_types.json](paragraph_types.json)
2. 复制其中一条已有 definition
3. 修改 `tag`、`display_name` 和你需要的字段
4. 保存文件
5. 启动程序，或者在程序已运行时重启程序

文件的整体结构是：

```json
{
  "definitions": [
    {
      "...": "一个段落类型定义"
    }
  ]
}
```

下面是一个最常用、可以直接复制的 `note` 示例：

```json
{
  "definitions": [
    {
      "tag": "note",
      "display_name": "Note",
      "render_kind": "decorated_text",
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
        "clean_to_tag": "body"
      },
      "export": {
        "markdown_prefix": "> ",
        "markdown_suffix": ""
      }
    }
  ]
}
```

你可以直接复制这个例子，然后修改：

- `tag`
- `display_name`
- `create_command`
- `prefix_text`
- `markdown_prefix`

保存后就可以作为你自己的段落类型使用。

## 完整配置结构说明

`definitions` 数组中的每一个对象，都是一个段落类型定义。  
当前代码实际可读取的结构来自 `ParagraphTypeSpec` 及其子配置块。

一个完整 definition 的形状大致如下：

```json
{
  "tag": "example",
  "display_name": "Example",
  "content_kind": "inline_text",
  "render_kind": "decorated_text",
  "uses_runs": true,
  "allows_text_input": true,
  "contagious": false,
  "allows_empty_persistence": true,
  "layout": {
    "rendered_font_size": 16,
    "line_height": 24.0,
    "top_margin": 0.0,
    "bottom_margin": 8.0,
    "left_margin": 0.0,
    "text_indent": 0.0,
    "prefixed_item_gap": 4.0,
    "prefix_gap": 6.0,
    "ordered_prefix_min_digits": 3,
    "expand_text_start": false
  },
  "text_style": {
    "color": null,
    "bold": null,
    "italic": null,
    "font_family": null
  },
  "decoration": {
    "prefix_kind": null,
    "prefix_text": null,
    "suffix_kind": null,
    "has_border": false,
    "has_background": false,
    "custom_renderer": null
  },
  "commands": {
    "create_command": null,
    "create_from_tag": "*",
    "clean_command": "/clean/",
    "clean_to_tag": null
  },
  "export": {
    "markdown_role": "paragraph",
    "markdown_prefix": null,
    "markdown_suffix": null
  }
}
```

注意：

- 这是“可配置字段全集”，不是“你必须全部写出来”
- 大多数自定义文本段落只需要写一小部分
- 某些可选数值字段在实际 JSON 中不建议显式写 `null`，更稳妥的方式是直接省略该字段

---

## 顶层字段

### `tag`

段落类型的唯一内部标识。

- 类型：字符串
- 必填：是
- 默认：无

说明：

- 必须是非空字符串
- 建议使用稳定的小写命名
- 不要和 builtin 类型重名

示例：

```json
"tag": "note"
```

### `display_name`

段落类型的显示名称。

- 类型：字符串
- 必填：否
- 默认：如果省略，会根据 `tag` 自动生成一个标题化名称

示例：

```json
"display_name": "Note"
```

### `content_kind`

控制段落内容的类型。

- 类型：字符串
- 必填：否
- 默认：`"inline_text"`

当前支持：

- `"inline_text"`：普通文本段落
- `"block_data"`：块级数据段落

对大多数用户自定义文本段落来说，保持默认即可。

### `render_kind`

控制段落的总体渲染方式。

- 类型：字符串
- 必填：否
- 默认：`"text"`

当前常用值：

- `"text"`：普通文本段落
- `"decorated_text"`：带装饰语义的文本段落
- `"custom_block"`：保留给特殊块渲染器

如果你定义的是普通可输入文本段落，通常使用 `"decorated_text"`。

### `uses_runs`

控制该段落是否使用普通文本 run 结构。

- 类型：布尔值
- 必填：否
- 默认：`true`

通常：

- 普通文本段落：保持 `true`
- 特殊 block 类型：可能会是 `false`

普通用户一般不需要改。

### `allows_text_input`

控制该段落是否允许直接输入文本。

- 类型：布尔值
- 必填：否
- 默认：`true`

通常：

- 普通文本段落：保持 `true`
- 特殊 block 类型：可能会是 `false`

普通用户一般不需要改。

### `contagious`

控制按 Enter 后，这个段落类型是否倾向于继续传染到下一段。

- 类型：布尔值
- 必填：否
- 默认：`false`

说明：

- `true`：回车后下一段可能继续保持这个类型
- `false`：回车后默认不继续这个类型

### `allows_empty_persistence`

控制这个类型在空段落时是否可以继续保持自己。

- 类型：布尔值
- 必填：否
- 默认：`true`

说明：

- `true`：空段落可以继续保留该类型
- `false`：空段落更偏向于过渡态 / 清理态

---

## `layout`

控制编辑器中的排版显示。

### `rendered_font_size`

段落在编辑器中的显示字号。

- 类型：整数
- 必填：否
- 默认：未设置时回退到系统默认正文字号

示例：

```json
"rendered_font_size": 18
```

### `line_height`

段落在编辑器中的行高。

- 类型：数字
- 必填：否
- 默认：未设置时按字号回退到默认行高

示例：

```json
"line_height": 26.0
```

### `top_margin`

段落上边距。

- 类型：数字
- 必填：否
- 默认：未设置时使用系统默认

### `bottom_margin`

段落下边距。

- 类型：数字
- 必填：否
- 默认：未设置时使用系统默认

### `left_margin`

段落左边距。

- 类型：数字
- 必填：否
- 默认：`0.0` 或系统默认

### `text_indent`

正文文本缩进。

- 类型：数字
- 必填：否
- 默认：`0.0`

### `prefixed_item_gap`

相邻带前标段落之间的垂直间距。

- 类型：数字
- 必填：否
- 默认：列表类段落会回退到系统默认值

这个字段主要用于列表样式或其他带前标段落的排版微调。

### `prefix_gap`

前标与正文之间的横向间距。

- 类型：数字
- 必填：否
- 默认：系统默认值

如果你定义了 `prefix_text` 或 `prefix_kind`，这个字段会影响前标与正文的距离。

### `ordered_prefix_min_digits`

有序列表前标最少保留的数字位数。

- 类型：整数
- 必填：否
- 默认：系统默认值

这个字段主要用于 `prefix_kind = "ordered_list"` 的情况。

### `expand_text_start`

是否为前标预留展开后的正文起始位置。

- 类型：布尔值
- 必填：否
- 默认：`false`

一般只有列表或显式带前标排版时才需要调整。

---

## `text_style`

控制该段落类型的默认文字样式覆盖。

这些字段属于“段落默认显示样式”，不是每个字符 run 的强制替换。

### `color`

默认文字颜色。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

示例：

```json
"color": "#123456"
```

### `bold`

默认是否加粗。

- 类型：布尔值或 `null`
- 必填：否
- 默认：`null`

### `italic`

默认是否斜体。

- 类型：布尔值或 `null`
- 必填：否
- 默认：`null`

### `font_family`

默认字体族。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

这个配置适合做“某类段落默认长成什么样”，比如代码行、强调块等。

---

## `decoration`

控制编辑器显示和复制输出时的前标或装饰语义。

它属于“编辑器 / 复制层配置”，不是 Markdown 导出配置。

### `prefix_kind`

一个语义化的前标类型，主要用于列表类行为。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

当前重要值：

- `"ordered_list"`
- `"unordered_list"`

如果你想要编号列表或项目符号列表，使用 `prefix_kind`。

### `prefix_text`

一个固定的可见前标。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

它会：

- 显示在编辑器里
- 出现在普通文本复制结果中

示例：

```json
"prefix_text": "※"
```

适合用来做固定标记，例如：

- `※`
- `!`
- `>>`

### `suffix_kind`

保留给后缀装饰语义的字段。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

当前普通用户通常不需要使用。

### `has_border`

是否带边框装饰。

- 类型：布尔值
- 必填：否
- 默认：`false`

### `has_background`

是否带背景装饰。

- 类型：布尔值
- 必填：否
- 默认：`false`

### `custom_renderer`

自定义渲染器名称。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

这是高级字段，通常用于特殊 block 渲染，不建议普通用户随意填写。

---

## `commands`

控制这个段落类型如何进入，以及如何清理回其他类型。

### `create_command`

创建该段落类型的命令。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

示例：

```json
"create_command": "/note/"
```

### `create_from_tag`

限制该命令只能从哪些源段落类型进入。

- 类型：字符串
- 必填：否
- 默认：`"*"`

示例：

```json
"create_from_tag": "body"
```

常见写法：

- `"body"`：只能从普通正文进入
- `"*"`：可以从任意段落类型进入

### `clean_command`

清理命令。

- 类型：字符串或 `null`
- 必填：否
- 默认：`"/clean/"`

如果你不特别修改，通常保持默认即可。

### `clean_to_tag`

清理时要回到的段落类型。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

示例：

```json
"clean_to_tag": "body"
```

---

## `export`

控制 Markdown 导出。

它和 `decoration` 是分开的：

- `decoration`：编辑器显示 / 普通文本复制
- `export`：Markdown 导出

### `markdown_role`

Markdown 导出角色。

- 类型：字符串或 `null`
- 必填：否
- 默认：`"paragraph"`

这个字段主要用于沿用系统内置的导出语义，比如：

- `"paragraph"`
- `"body"`
- `"ordered_item"`
- `"unordered_item"`
- `"heading_1"`、`"heading_2"` 等

普通用户如果只想定义自定义前后缀，通常不需要改它。

### `markdown_prefix`

导出为 Markdown 时，加在正文前面的内容。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

示例：

```json
"markdown_prefix": "> "
```

### `markdown_suffix`

导出为 Markdown 时，加在正文后面的内容。

- 类型：字符串或 `null`
- 必填：否
- 默认：`null`

示例：

```json
"markdown_suffix": ""
```

如果没有写 `export`，系统会继续使用该段落类型当前的默认 Markdown 导出行为。

---

## 示例：`note` 段落

请直接使用下面这个示例作为起点：

```json
{
  "tag": "note",
  "display_name": "Note",
  "render_kind": "decorated_text",
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
    "clean_to_tag": "body"
  },
  "export": {
    "markdown_prefix": "> ",
    "markdown_suffix": ""
  }
}
```

它的含义是：

- 在 `body` 段落中输入 `/note/`，可以进入 `note`
- 编辑器和普通文本复制时，前标是 `※`
- 导出 Markdown 时，前缀是 `> `

也就是说，当一个 `note` 段落内容是 `hello` 时：

- 编辑器 / 普通文本复制：`※hello`
- Markdown 导出：`> hello`

## 输入、显示、复制、导出的关系

这几个层面是故意分开的：

- `commands`：控制怎么输入这个段落类型
- `decoration`：控制编辑器里怎么显示、普通文本复制时前标是什么
- `export`：控制 Markdown 导出格式

例如：

- `create_command: "/note/"`
- `decoration.prefix_text: "※"`
- `export.markdown_prefix: "> "`

它的意思是：

- 你通过 `/note/` 进入这个类型
- 编辑器和普通文本复制里看到的是 `※`
- Markdown 导出时使用的是 `> `

不要把 `decoration` 和 `export` 混为一个字段。

## 错误配置与安全降级

即使配置写错，程序也不会因为 `paragraph_types.json` 崩溃。

当前有安全降级机制：

- `paragraph_types.json` 不存在：忽略用户配置，只使用 builtin 类型
- 文件读取失败：忽略用户配置，只使用 builtin 类型
- JSON 非法：忽略用户配置，只使用 builtin 类型
- 顶层结构不对：忽略
- 某一条 definition 写错：只跳过这一条
- 与 builtin `tag` 冲突：跳过该定义
- 同文件内 `tag` 重复：后面的重复项会被跳过

因此：

- 一条坏 definition 不会影响其他合法 definition
- 整个文件损坏也不会导致程序无法启动

## 使用建议

- 先从 `note` 示例复制开始
- 一次只改一个字段，方便排查
- 保持 `tag` 唯一
- 尽量让 `create_command` 也保持唯一
- `prefix_text` 用于编辑器显示和普通文本复制
- `markdown_prefix` / `markdown_suffix` 只用于 Markdown 导出
- 如果你不确定高级字段是否需要，先不要写，保持省略通常更安全
