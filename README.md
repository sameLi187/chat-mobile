# 起源 S1 配置清单 (1-50)

本清单用于快速调整第一版游戏配置，覆盖聊天社交+RPG 前 50 级核心参数。

当前实现位置：

- 后端核心：`backend/main.py`
- 依赖：`backend/requirements.txt`
- 手机端：`mobile/App.js`

---

## 1. S1 目标边界

- 等级上限：`50`
- 装备最高品质（S1）：`史诗`
- S1 开放品质：`普通(白)`、`优秀(绿)`、`精良(蓝)`、`史诗(紫)`
- S1 不开放：`传奇(黄)`、`神话(红)`
- 角色初始：无职业差异，全部同模板
- 职业特性来源：通过史诗套装 `2/4/6` 件激活

---

## 2. 地图与等级段

| 地图ID | 地图名 | 等级段 | 定位 |
|---|---|---|---|
| M01 | 雾隐林地 | 1-12 | 新手野区 |
| M02 | 断碑荒原 | 13-22 | 过渡野区 |
| M03 | 黑岩峡谷 | 23-32 | 30套前置区 |
| M04 | 霜骸墓园 | 33-42 | 40套主刷区 |
| M05 | 深渊边庭 | 43-50 | 50套毕业区 |

---

## 3. 角色与怪物属性体系

S1 不再只看 `power`，实际战斗同时参考以下属性：

- `hp`：生命
- `attack`：攻击
- `defense`：防御
- `dodge`：闪避
- `crit`：暴击
- `block`：格挡
- `lifesteal`：吸血

说明：

- `power` 仍保留为综合展示值
- 野怪 / Boss / 副本首领也会按等级生成同维度属性
- 胜率与通关率改为按玩家总属性对比怪物属性估算，不再出现“10级角色高概率越级打40级内容”的旧问题

### 3.1 野怪与Boss命名

| 地图 | 野怪 | 精英 | Boss |
|---|---|---|---|
| 雾隐林地 | 雾牙幼兽 | 腐爪监视者 | 迷雾树心魔 |
| 断碑荒原 | 断碑掠夺者 | 荒原血鬃 | 碎碑战将 |
| 黑岩峡谷 | 黑岩蛮卒 | 熔痕督军 | 裂炉巨像 |
| 霜骸墓园 | 霜墓巡魂 | 寒棺守卫 | 白骨霜后 |
| 深渊边庭 | 渊庭魔仆 | 裂隙执刑官 | 边庭深渊主 |

### 3.2 怪物强度系数

基线：同等级普通怪 = `1.0`

| 类型 | 属性倍率 | 说明 |
|---|---:|---|
| 野外普通怪 | 1.0 | 当前地图基础怪 |
| 野外精英怪 | 2.2 | 明显高于同级散件角色 |
| 地图Boss | 4.8 | 会掉抽奖券 |
| 30副本Boss | 4.8 | 进本仅等级；通关仍建议 20+ 级段史诗装支撑属性 |
| 40副本Boss | 7.2 | 进本仅等级；通关仍建议 30 史诗套水平属性 |
| 50副本Boss | 9.2 | 进本仅等级；通关仍建议 40 史诗套水平属性 |

---

## 4. 副本门槛 (已实现)

| 副本ID | 副本名 | 进入等级 | 说明 |
|---|---|---:|---|
| DUN30 | 黑岩熔炉 | `Lv30` | 仅等级达标即可进入 |
| DUN40 | 霜骨王庭 | `Lv40` | 仅等级达标即可进入 |
| DUN50 | 深渊裂隙 | `Lv50` | 仅等级达标即可进入 |

说明：

- **进入副本**：只校验 `玩家等级 >= 推荐等级`，不再检查史诗件数、套装或总属性。
- **副本内战斗**：仍按 Boss 属性与玩家 `total_stats` 估算通关率；装备差时可能通关率很低或失败，这是战斗结果而非进本门槛。

---

## 5. 副本内部命名

| 副本 | 小怪 | 精英 | 最终Boss |
|---|---|---|---|
| 黑岩熔炉 | 灰烬铸奴 | 熔链监工 | 熔炉之心·格罗姆 |
| 霜骨王庭 | 霜庭遗臣 | 寒冠行刑者 | 霜王遗骸·维尔萨 |
| 深渊裂隙 | 裂隙吞徒 | 深渊司判 | 裂界魔君·阿扎克 |

---

## 6. 装备命名规则

- 白装：`普通{部位}·Lv{等级}`
- 绿装：`优秀{部位}·Lv{等级}`
- 蓝装：`精良{部位}·Lv{等级}`
- 紫装：`{史诗套装名}{部位}·Lv{等级}`

部位固定：`weapon`、`helmet`、`chest`、`gloves`、`pants`、`boots`

---

## 7. 白绿蓝与史诗数值公式

### 6.1 等级系数

`等级系数 = 1 + (Lv - 1) * 0.055`

### 6.2 品质系数

- 普通：`1.00`
- 优秀：`1.18`
- 精良：`1.40`
- 史诗：`1.75`（用于史诗基础强度）

### 6.3 基础模板（Lv1 白装）

| 部位 | 战力 | 生命 | 攻击 | 防御 | 闪避 | 暴击 | 格挡 |
|---|---:|---:|---:|---:|---:|---:|---:|
| weapon | 20 | 0 | 20 | 0 | 0% | 2% | 0% |
| helmet | 12 | 30 | 0 | 12 | 1% | 0% | 2% |
| chest | 24 | 60 | 0 | 24 | 0% | 0% | 3% |
| gloves | 10 | 12 | 5 | 10 | 2% | 3% | 0% |
| pants | 18 | 45 | 0 | 18 | 1% | 0% | 2% |
| boots | 9 | 20 | 0 | 9 | 4% | 0% | 0% |

计算结果写入：

- `game_items.power`
- `game_items.hp`
- `game_items.attack`
- `game_items.defense`
- `game_items.dodge`
- `game_items.crit`
- `game_items.block`
- `game_items.lifesteal`

史诗装备会在基础模板上额外获得更高倍率，并按套装方向补强：

- 均衡系：生命 / 防御 / 攻击均衡成长
- 单点爆发系：攻击 / 暴击更高
- AOE系：攻击 / 暴击 / 闪避更高
- 坦回复系：生命 / 格挡 / 吸血更高

---

## 8. 史诗套装列表

### 30 级史诗

- 铁壁战痕（均衡）
- 猎风断星（单点爆发）
- 霜火共鸣（范围AOE）
- 圣辉庇护（坦度回复）

### 40 级史诗

- 不屈征伐（均衡）
- 寂灭猎神（单点爆发）
- 万象崩界（范围AOE）
- 誓约圣裁（坦度回复）

### 50 级史诗

- 深渊统御（均衡）
- 终夜裁决（单点爆发）
- 虚空洪流（范围AOE）
- 光耀圣域（坦度回复）

---

## 9. 套装激活效果规则

统一规则：`2件` / `4件` / `6件` 激活

实现表：`set_bonuses`

示例：

- 2件：基础倾向（输出/生存/范围/回复）
- 4件：核心机制（穿刺、连锁、护盾、震荡等）
- 6件：职业特性级机制（毕业效果）

---

## 10. 词条池（当前已实现首版）

### 9.1 当前已实现

首版词条系统为“实例化掉落词条”：

- 仅 `史诗武器` 掉落时随机生成词条
- 同一把武器掉两次，词条可以不同
- 词条存放在 `player_inventory`，不是写死在 `game_items`
- 当前每把史诗武器随机获得 `1-3` 条词条

### 9.2 当前史诗武器词条池

| 词条 | 效果方向 |
|---|---|
| 暴伤 | 增加暴击伤害 |
| 冰冻 | 增加冰冻几率 |
| 格挡 | 增加格挡率 |
| 吸血 | 增加生命偷取 |
| 锋锐 | 直接增加攻击 |
| 致命 | 增加暴击率 |

### 9.3 后续可扩展方向

- 输出：攻击%、攻速、对Boss增伤、穿透
- 生存：生命%、护甲%、受疗加成
- 控制：冰冻时长、眩晕几率
- 防御：格挡减伤、低血减伤
- 循环：冷却缩减、回能、资源消耗降低

---

## 10.1 职业特性技能书规模（已扩充）

当前已将职业特性技能书扩充为：

- `iron（铁壁）`：至少 `20` 本
- `hunt（猎杀号）`：至少 `20` 本
- `arc（崩界）`：至少 `20` 本
- `pal（圣裁）`：至少 `20` 本

并额外提供每个特性的首领掉落技能书，用于碎片兑换与终局构筑。

---

## 11. 背包、分类与出售

### 背包当前已支持

- 查看背包物品
- 穿戴装备
- 装备/道具分类筛选
- 品质筛选
- 出售不要的物品
- 显示单件装备详细属性
- 显示装备随机词条
- 显示角色总属性面板

### 分类规则

当前 `game_items.category` 支持：

- `equipment`：装备
- `consumable`：道具

### 出售规则

- 接口：`POST /game/sell`
- 已穿戴装备不能出售
- 出售后金币直接进入 `player_wallet.gold`
- 当前默认出售数量：`1`

---

## 12. 抽奖券与掉落规则（方向）

- Boss 掉落抽奖券
- 普通Boss：普通券为主
- 高级/终局Boss：高级券概率更高
- 当前不做保底（纯概率）
- 普通池 / 高级池 都可抽到：
  - 金币
  - 强化石
  - 重铸石
  - 史诗碎片（高级池）
  - 装备
  - 道具（消耗品）

---

## 13. 数据库表清单 (S1)

### 社交与账号

- `users`
- `friend_requests`
- `groups`
- `group_members`

### 游戏核心

- `player_progress`
- `player_inventory`
- `player_wallet`
- `game_items`
- `set_bonuses`
- `dungeons_game`

`player_inventory` 当前额外承载：

- `affix_json`
- `bonus_hp`
- `bonus_attack`
- `bonus_defense`
- `bonus_dodge`
- `bonus_crit`
- `bonus_block`
- `bonus_lifesteal`
- `bonus_crit_damage`
- `bonus_freeze`

---

## 14. 后端 API 清单 (S1)

### 账号与社交

- `POST /auth/register`
- `POST /auth/login`
- `GET /auth/me`
- `GET /friends`
- `GET /friends/pending`
- `POST /friends/request`
- `POST /friends/accept`
- `POST /groups`
- `GET /groups/my`
- `POST /groups/{group_id}/members`
- `WS /ws`（大厅/私聊/群聊）

### 游戏接口

- `GET /game/bootstrap`：读取地图/怪物/副本规则
- `GET /game/profile`：玩家等级、战力、总属性、穿戴、套装激活
- `GET /game/inventory`：背包、装备单件属性、随机词条
- `POST /game/equip`：穿戴装备
- `POST /game/sell`：出售背包物品
- `POST /game/dungeon/challenge`：副本进入校验（仅等级）
- `POST /game/fight/monster`：刷怪结算，并返回怪物属性/估算胜率
- `POST /game/fight/engage`：进入非回合制战斗，返回本场怪物配置、玩家普攻CD与六技能栏数据
- `POST /game/fight/commit`：提交战斗结算（奖励、掉落、技能掉落）
- `GET /game/skills/shop`：技能商店列表（金币购买）
- `POST /game/skills/buy`：购买技能
- `POST /game/skills/loadout`：保存六技能栏配置（按六部位栏位）
- `POST /game/skills/refresh`：刷新技能商店（金币消耗递增）
- `GET /game/skills/mastery`：查询技能熟练度与专精分支
- `POST /game/skills/specialize`：切换技能专精分支（爆发/续航/控制）
- `POST /game/skills/scrap`：分解技能为技能碎片
- `POST /game/skills/exchange`：技能碎片兑换Boss掉落技能
- `POST /game/sell/batch`：按等级/品质条件一键出售
- `POST /game/dungeon/settle`：副本结算，并返回Boss属性/估算通关率
- `POST /game/dungeon/event-roll`：按权重抽取当前房间事件选项（支持互斥标签）
- `GET /game/balance/config`：读取可调数值总表（仅管理员）
- `POST /game/balance/config`：更新可调数值总表（仅管理员）
- `POST /game/gacha/draw`：抽奖

---

## 15. 手机端当前可试玩内容

App 当前已支持两个模式：

- `聊天社交`
  - 世界大厅
  - 私聊
  - 群聊
  - 好友
- `RPG试玩`
  - 查看角色资料
  - 查看角色生命/攻击/防御/闪避/暴击/格挡/吸血
  - 查看角色暴伤加成 / 冰冻几率
  - 非回合制刷怪战斗界面（实时掉血、普攻/技能CD）
  - 普通怪仅普攻、精英怪1个小技能、地图Boss额外多技能
  - 玩家普攻CD按攻速（攻击）动态计算
  - 六技能栏绑定六部位，需对应部位穿戴史诗及以上装备才解锁
  - 技能支持金币商店购买与Boss掉落
  - 技能栏支持“点击弹窗选择全部可用技能”与清空
  - 战斗界面支持自动普攻开关
  - 战斗界面加入角色/怪物立绘区与受击闪烁反馈
  - 战斗加入动作感参数：前摇、后摇、打断硬直、伤害数字飘字
  - 怪物技能支持条件触发（低血狂暴、连招触发）
  - 副本房间加入可交互事件（宝箱三选一、祭坛增益/代价、精英词缀风险收益）
- 副本事件改为后端权重池抽取，可通过配置表扩展新事件
  - 技能成长支持熟练度与专精分支
  - 技能商店支持轮换刷新与碎片定向兑换
  - 背包支持按等级/品质的一键出售
- 数值总表接口支持管理员调参（不对普通玩家前端暴露）
  - 检查副本等级（达标即可进本）
  - 副本结算
  - 抽奖
  - 背包筛选
  - 查看装备单件属性 / 随机词条
  - 背包显示装备贴图（白绿蓝共用底图，史诗按套装图）
  - 角色已穿戴 6 部位单独图标栏，可点击查看详情/替换装备
  - 刷怪 / 副本 / 抽奖结果改为弹窗层展示贴图与奖励
  - 结果弹窗加入史诗紫光、抽奖闪屏感、Boss 掉落标题强化
  - 史诗掉落卡片加入脉冲呼吸动画与入场缩放
  - 抽奖结果加入先翻牌再显示奖励的两段式表现
- 地图 / 野怪 / 精英 / Boss / 副本已替换为正式命名展示
- 副本内部小怪 / 精英 / 最终Boss 已补全正式命名
  - 穿戴 / 出售

---

## 16. 副本UI与资源接入规范

当前已在前端接入“副本 UI 框架”，包括：

- 副本选择卡片
- 副本背景占位区
- Boss 头像占位区
- 房间节点路线
- 进入副本后的独立弹窗面板
- 已接入真实副本背景图 / Boss 图 / 节点图资源映射

建议资源目录：

- `mobile/assets/dungeons/backgrounds/DUN30.png`
- `mobile/assets/dungeons/backgrounds/DUN40.png`
- `mobile/assets/dungeons/backgrounds/DUN50.png`
- `mobile/assets/dungeons/bosses/DUN30.png`
- `mobile/assets/dungeons/bosses/DUN40.png`
- `mobile/assets/dungeons/bosses/DUN50.png`
- `mobile/assets/dungeons/nodes/normal.png`
- `mobile/assets/dungeons/nodes/elite.png`
- `mobile/assets/dungeons/nodes/treasure.png`
- `mobile/assets/dungeons/nodes/heal.png`
- `mobile/assets/dungeons/nodes/boss.png`

后续接图规则：

- `DUN30` 对应 `黑岩熔炉`
- `DUN40` 对应 `霜骨王庭`
- `DUN50` 对应 `深渊裂隙`
- 文件命名建议统一使用 `.png`
- 在未接入真实图片前，前端会先显示占位块和预留路径提示

### 16.1 已创建目录

- `mobile/assets/dungeons/backgrounds/`
- `mobile/assets/dungeons/bosses/`
- `mobile/assets/dungeons/nodes/`

### 16.2 文件路径与中文提示词

#### 副本背景

建议出图规格：

- 方向：`横版`
- 比例：`16:9`
- 建议尺寸：`1920x1080`
- 生成时建议额外加：`横向构图，适合作为游戏战斗背景，画面中部保留角色站位空间`

- `mobile/assets/dungeons/backgrounds/DUN30.png`
  - `暗黑幻想风副本背景，黑岩熔炉场景，巨大黑色岩壁，熔炉平台，熔岩裂缝，火星飞散，铁链悬挂，古老锻造结构，地面有灼热红光，整体氛围厚重压迫，像远古魔族铸造工坊，横向构图，适合ARPG副本战斗背景，无人物，无文字，无水印`

- `mobile/assets/dungeons/backgrounds/DUN40.png`
  - `暗黑幻想风副本背景，霜骨王庭场景，冰霜王座废墟，寒冰台阶，苍白骨柱，王庭遗迹，冷蓝色寒气弥漫，霜雪覆盖地面，残破王座与巨型冰棺，整体气氛阴冷肃杀，像被遗忘的亡者王庭，横向构图，适合ARPG副本战斗背景，无人物，无文字，无水印`

- `mobile/assets/dungeons/backgrounds/DUN50.png`
  - `暗黑幻想风副本背景，深渊裂隙场景，漂浮断裂石台，巨大的虚空裂缝，紫黑色能量洪流，深渊符文，空间扭曲感，裂隙边缘有邪异辉光，背景深不见底，整体氛围危险诡异，像世界边界被撕开的禁地，横向构图，适合ARPG副本战斗背景，无人物，无文字，无水印`

#### 节点图标

建议出图规格：

- 方向：`正方形`
- 比例：`1:1`
- 建议尺寸：`1024x1024`
- 生成时建议额外加：`图标化设计，主体居中，轮廓清晰，透明背景感`

- `mobile/assets/dungeons/nodes/normal.png`
  - `暗黑幻想风UI节点图标，普通战斗房图标，黑铁圆形徽记，中间是交叉短剑和暗红微光，风格简洁清晰，适合手游副本路线节点，图标化表现，透明背景感，无文字，无水印`

- `mobile/assets/dungeons/nodes/elite.png`
  - `暗黑幻想风UI节点图标，精英房图标，锋利黑金徽记，中间是异化头盔或怪物面甲，带紫红危险光纹，气质更凶狠更稀有，适合手游副本路线节点，图标化表现，透明背景感，无文字，无水印`

- `mobile/assets/dungeons/nodes/treasure.png`
  - `暗黑幻想风UI节点图标，宝箱房图标，古老金属宝箱，暗金与棕铜材质，箱缝中透出柔和金光，带稀有奖励感，适合手游副本路线节点，图标化表现，透明背景感，无文字，无水印`

- `mobile/assets/dungeons/nodes/heal.png`
  - `暗黑幻想风UI节点图标，恢复房图标，神秘圣杯或恢复祭坛图标，带柔和青蓝色圣光和净化气息，显得安全、治愈、短暂休整，适合手游副本路线节点，图标化表现，透明背景感，无文字，无水印`

- `mobile/assets/dungeons/nodes/boss.png`
  - `暗黑幻想风UI节点图标，Boss房图标，巨大恶魔角冠徽记，黑红紫配色，中心是压迫感眼瞳或王冠轮廓，气质威严危险，明显高于普通节点，适合手游副本路线节点，图标化表现，透明背景感，无文字，无水印`

#### Boss 占位图

建议出图规格：

- 方向：`竖版`
- 比例：`4:5`
- 建议尺寸：`1024x1280`
- 生成时建议额外加：`半身像或近景全身像，主体居中，不要过度贴边`

- `mobile/assets/dungeons/bosses/DUN30.png`
  - `暗黑幻想风Boss半身像，熔炉之心·格罗姆，巨型熔岩铸铁魔像首领，黑铁重甲般的身体结构，胸口有熔炉核心发出炽热红光，肩部粗壮，熔火在裂缝中流动，充满压迫感与古老锻造怪物气质，半身构图，适合手游Boss展示卡面，无文字，无水印`

- `mobile/assets/dungeons/bosses/DUN40.png`
  - `暗黑幻想风Boss半身像，霜王遗骸·维尔萨，冰霜骸骨女王，残破王冠，白骨面容，寒霜披风，冰蓝色幽光眼眸，骨甲与王族装饰并存，气质高贵而阴冷，像亡者王庭的最后统治者，半身构图，适合手游Boss展示卡面，无文字，无水印`

- `mobile/assets/dungeons/bosses/DUN50.png`
  - `暗黑幻想风Boss半身像，裂界魔君·阿扎克，深渊恶魔君主，紫黑铠甲，双角王者轮廓，身上有裂界符文与虚空能量翻涌，背景带扭曲空间和深渊裂缝感，气质像终局级别的深渊统治者，半身构图，适合手游Boss展示卡面，无文字，无水印`

---

## 17. 套装贴图提示词

统一约束：

- 风格：`暗黑ARPG装备图标`
- 视角：`正视或轻微三分之四视角`
- 背景：`纯深色透明背景感`
- 用途：`手游背包小图标`
- 质感：`高对比、锐利边缘、可读性强`
- 禁止：`不要角色立绘、不要复杂场景、不要文字水印`

通用后缀提示词，可直接拼接在每一套前面：

`dark fantasy action RPG equipment icon, mobile inventory icon, high readability, polished metal and cloth materials, centered composition, dark background, dramatic rim light, detailed but clean silhouette, no character, no text, no watermark`

### 15.1 铁壁战痕

`a dark fantasy heavy armor set icon collection, iron fortress theme, scarred steel plates, worn battle marks, thick pauldrons, square silhouette, ash black metal with dim crimson grooves, tanky and disciplined feeling`

### 15.2 猎风断星

`a dark fantasy agile hunter set icon collection, wind slash theme, sleek leather and alloy armor, narrow sharp edges, split feather motifs, dark emerald and silver accents, assassin precision, burst damage feeling`

### 15.3 霜火共鸣

`a dark fantasy elemental battlemage set icon collection, frost and fire dual-core theme, blue-red energy veins, arcane crystal inlays, flowing layered cloth and armor mix, explosive aoe feeling`

### 15.4 圣辉庇护

`a dark fantasy holy guardian set icon collection, sacred protection theme, pale gold and ivory armor, chapel-like engravings, soft radiant glow, shielded and healing feeling, paladin style`

### 15.5 不屈征伐

`a dark fantasy warlord armor set icon collection, relentless conquest theme, rugged bronze-black armor, cracked runes, brutal frontline silhouette, durable and aggressive balanced fighter feeling`

### 15.6 寂灭猎神

`a dark fantasy executioner hunter set icon collection, godslayer theme, matte black alloy, deep purple edge highlights, predatory narrow shapes, extreme single-target burst feeling`

### 15.7 万象崩界

`a dark fantasy cataclysm caster set icon collection, world-shattering arcane theme, fractured void crystals, violet-blue energy streams, unstable magical armor pieces, large scale aoe destruction feeling`

### 15.8 誓约圣裁

`a dark fantasy oathbound crusader set icon collection, sacred judgment theme, heavy silver-gold armor, engraved vow seals, divine barrier motif, protector and healer feeling`

### 15.9 深渊统御

`a dark fantasy abyss overlord set icon collection, abyss control theme, obsidian armor with crimson core glow, monarch silhouette, oppressive balanced endgame power feeling`

### 15.10 终夜裁决

`a dark fantasy eternal night execution set icon collection, midnight assassin theme, black-red blade motifs, razor sharp segmented armor, fatal burst feeling, endgame predator`

### 15.11 虚空洪流

`a dark fantasy void surge set icon collection, cosmic collapse theme, dark indigo armor, void cracks, luminous swirling energy, devastating aoe spellblade feeling`

### 15.12 光耀圣域

`a dark fantasy radiant sanctuary set icon collection, ultimate holy fortress theme, radiant white-gold armor, halo-like engravings, sanctuary barrier and healing presence, endgame guardian feeling`

### 15.13 套装代号对照表

| 内部代号 | 中文套装名 | 战斗定位 | 贴图关键词 |
|---|---|---|---|
| `set30_iron` | 铁壁战痕 | 均衡、攻防一体、站桩推进 | 黑铁重甲、战痕划痕、暗红熔纹、厚重轮廓 |
| `set30_hunt` | 猎风断星 | 单点爆发、快速处决 | 轻甲皮革、锋利刃片、深绿银灰、疾风感 |
| `set30_arc` | 霜火共鸣 | 范围AOE、元素爆发 | 冰火双元素、蓝红能量纹、晶体镶嵌、法甲混合 |
| `set30_pal` | 圣辉庇护 | 坦度回复、守护续航 | 象牙白金、圣光流纹、教会雕纹、庄严厚甲 |
| `set40_iron` | 不屈征伐 | 均衡加强、持续作战 | 黑铜旧钢、裂纹符文、战争磨损、前线统帅感 |
| `set40_hunt` | 寂灭猎神 | 极致单杀、暴击斩杀 | 暗黑金属、深紫辉边、狭长锐利、猎杀号感 |
| `set40_arc` | 万象崩界 | 大范围清场、法术倾泻 | 虚空裂隙、破碎晶体、紫蓝能流、灾厄法装 |
| `set40_pal` | 誓约圣裁 | 高抗反击、护盾恢复 | 银白金甲、誓约纹章、圣裁浮雕、神圣壁垒 |
| `set50_iron` | 深渊统御 | 终局均衡、全能压制 | 黑曜石甲、猩红核心、君主轮廓、深渊压迫 |
| `set50_hunt` | 终夜裁决 | 终局单点、夜刃爆发 | 黑红刀锋甲片、处刑者造型、夜袭气质、致命感 |
| `set50_arc` | 虚空洪流 | 终局AOE、虚空轰炸 | 深靛紫黑、旋涡流纹、虚空裂痕、能量洪流 |
| `set50_pal` | 光耀圣域 | 终局坦辅、圣域守护 | 白金圣甲、圣域结界纹、辉光边缘、神圣堡垒 |

---

## 18. 本轮更新记录

本轮已根据测试反馈调整：

- 装备不再只有 `战力`
- 角色总属性加入 `生命/攻击/防御/闪避/暴击/格挡/吸血`
- 野怪与副本 Boss 改为按真实属性生成
- 胜率 / 通关率改为属性对比估算，不再只靠简单战力概率
- 副本进入改为仅等级门槛；套装/属性不再拦截进本（通关率仍受属性影响）
- 史诗武器加入实例化随机词条
- 前端已接入装备贴图资源映射
- 已穿戴栏与掉落/抽奖结果贴图卡片已接入
- 已穿戴 6 格支持点击详情与快速替换
- 战斗 / 副本 / 抽奖结果改为真实弹窗层
- 结果弹窗已加入稀有掉落视觉强化
- 史诗卡片动画与抽奖翻牌演出已接入
- 对玩家可见的地图/怪物/副本名称已正式化
- 副本内部生物命名与展示已补全
- 副本资源目录已创建，并补全了对应中文提示词
- 副本真实图片资源已接入前端展示
- 后端支持 `DATABASE_PATH` / `SQLITE_DB_PATH`，便于 Railway 等环境把 SQLite 放到持久卷，避免重部署清空用户数据
- 新增非回合制战斗流：`engage + commit` 双接口，支持实时HP变化、怪物技能CD与玩家六技能栏
- 新增技能系统：`game_skills / player_skills / player_skill_loadout` 与技能商店/掉落/装备配置
- 新增 `owned_skills` 角色字段，前端可弹窗展示栏位全部可选技能
- 非回合制战斗新增自动普攻开关与受击闪烁表现，战斗视觉更接近正式手游
- 战斗逻辑新增“前摇/后摇/硬直/打断/飘字”与怪物条件触发AI（低血、连招）
- 副本房间事件可交互并影响本次副本结算（通关率/奖励/Boss强度）
- 技能系统新增熟练度与专精树，商店支持轮换刷新，Boss技能支持碎片兑换
- 每个职业特性技能书已扩到至少20本（iron/hunt/arc/pal），并补充特性首领掉落技能书
- 新增背包一键出售（等级/品质条件过滤）
- 新增 GM 数值总表接口：`GET/POST /game/balance/config`，仅管理员可调用
- 新增副本事件权重池接口：`POST /game/dungeon/event-roll`，支持互斥标签与历史去重
- 实时战斗怪物 AI 支持配置化策略参数（触发优先级、连招倾向）
- 战斗日志降噪：普通伤害以飘字为主，仅保留关键事件日志
- 结果弹窗支持高稀有度先揭示再翻牌词条，多掉落按价值排序展示
- 副本新增诅咒/贪婪风险轨道：风险越高，后续难度和收益同步提升
- 每个Boss补充可识别机制（护盾/召唤/狂暴）并接入战斗与结算
- 升级经验改为逐级递增曲线，副本经验与玩家等级联动缩放
- 每次功能更新都同步维护本 README

---

## 19. 可调参数入口（建议优先）

已新增统一数值配置表：`game_balance_config`（`domain + key_name + value_json`）。

后端会在 `init_db()` 时自动补齐默认配置，核心逻辑均改为**优先读配置表**：

- `equipment`：装备品质倍率、部位基础属性、套装额外加成、出售价格公式系数
- `monster`：地图等级上限、怪物奖励参数、怪物战斗快照公式、胜率估算参数、怪物技能模板
- `drop`：技能书掉率、装备品质掉率权重
- `shop`：技能商店展示数量、刷新费用、碎片分解/兑换消耗
- `skill`：普攻CD公式、熟练度阈值、专精分支加成系数
- `dungeon`：房间事件池、事件权重、互斥标签、每房间展示数量

你后续要调平衡时，优先改 `game_balance_config.value_json`，无需改 Python 代码。

---

## 20. 本地运行

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

健康检查：

- `GET /health`
- `GET /game/bootstrap`（需 Bearer token）

---

## 21. 线上部署与用户数据持久化（SQLite + 持久卷）

默认情况下，数据库文件在 `backend/chat.db`（与代码同目录）。在 Docker / Railway 等平台**每次重新部署**时，若未挂载持久存储，该文件会随容器文件系统一起丢失，表现为「一更新游戏内容，老账号没了」。

后端已支持通过环境变量把库放到持久卷上（二选一，推荐前者）：

| 变量名 | 说明 |
|---|---|
| `DATABASE_PATH` | SQLite 文件的**绝对路径**，例如 `/data/chat.db` |
| `SQLITE_DB_PATH` | 与上一行等价，兼容备用命名 |
| `CONFIG_ADMIN_USERNAME` | 可调数值接口管理员用户名（建议设置为你的账号名） |
| `CONFIG_ADMIN_KEY` | 可调数值接口管理员密钥（强随机字符串，调用时放请求头） |

**Railway 推荐做法：**

1. 在服务里添加 **Volume（持久卷）**，挂载路径设为例如 `/data`。
2. 在 Variables 里设置 `DATABASE_PATH=/data/chat.db`。
3. 重新部署后，日志里会出现一行：`[db] sqlite path: /data/chat.db`，用于确认已指向卷。
4. 同时务必设置强随机 `JWT_SECRET`，否则每次部署若密钥变化，旧 token 会全部失效（账号仍在，但需要重新登录）。
5. 若需启用“仅你可调参”，请设置 `CONFIG_ADMIN_USERNAME` + `CONFIG_ADMIN_KEY`；调用 `/game/balance/config` 时需带 `X-Admin-Key` 请求头。

说明：首次把库迁到卷上之后，旧容器内的 `backend/chat.db` 不会自动合并进新路径；若需要迁数据，应在切换变量前自行备份旧库并上传到卷（或短暂同时保留两路径由运维手动合并）。
