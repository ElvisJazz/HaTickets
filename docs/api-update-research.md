# 大麦 API 更新调研报告

> 调研日期：2026-03-29
> 目的：对比项目中使用的 mtop API 与大麦当前线上版本的差异，指导后续更新

---

## 一、本次已完成的改动

### 1.1 配置集中化重构

将所有易变参数从代码中提取到两个集中配置文件，后续大麦更新只需改配置：

| 配置文件 | 语言 | 包含内容 |
|----------|------|----------|
| `desktop/src/utils/dm/dm-config.js` | JS | appKey、Baxia SDK URL、订单字段名、错误关键词 |
| `desktop/src-tauri/src/dm_config.rs` | Rust | jsv、appKey、UA、各接口版本号、URL 构建函数 |

**影响的文件：**
- `crypto.js` — appKey 改为引用 `DM_APP_KEY`
- `baxia.js` — CDN URL 改为引用常量
- `api-utils.js` — 所有字段名引用配置，错误提示增强
- `main.rs` — UA/SEC_CH_UA 引用常量，5 个 API URL 使用 `build_base_url()` 重构
- `lib.rs` — 注册 `dm_config` 模块
- `dm.vue` — Baxia 加载失败提示改善

### 1.2 get_product_info 接口已更新

根据用户抓包数据，商品详情接口已完成更新：

**旧接口（项目原始）：**
```
API:  mtop.alibaba.damai.detail.getdetail
Path: /1.2/
jsv:  2.7.2
v:    2.0
type: originaljson
data: {"itemId":"xxx","bizCode":"ali.china.damai","scenario":"itemsku",
       "exParams":"{\"dataType\":4,\"dataId\":\"\",\"privilegeActId\":\"\"}",
       "dmChannel":"damai@damaih5_h5"}
其他: AntiFlood=true, method=GET, tb_eagleeyex_scm_project=...
```

**新接口（已更新到代码）：**
```
API:  mtop.damai.item.detail.getdetail
Path: /1.0/
jsv:  2.7.5
v:    1.0
type: json
data: {"itemId":"xxx","platform":"8","comboChannel":"2",
       "dmChannel":"damai@damaih5_h5"}
其他: timeout=10000, valueType=string, forceAntiCreep=true
      （移除了 AntiFlood, method, tb_eagleeyex_scm_project）
```

**对应代码位置：** `main.rs:61-73` (`get_info` 函数)

---

## 二、各接口当前状态（探测结果）

通过直接调用 mtop 端点（使用假签名），探测各接口存活状态：

| 接口 | 端点名 | 版本 | 探测响应 | 状态判断 |
|------|--------|------|----------|----------|
| 商品详情 | `mtop.damai.item.detail.getdetail` | 1.0 | `令牌为空` | ✅ 新端点，已更新 |
| 票档列表 | `mtop.alibaba.detail.subpage.getdetail` | 2.0 | `USER_VALIDATE`(CAPTCHA) | ⚠️ 端点存在，但可能有变化 |
| 观演人 | `mtop.damai.wireless.user.customerlist.get` | 2.0 | `Session过期` | ✅ 端点正常 |
| 确认订单 | `mtop.trade.order.build.h5` | 4.0 | `Session过期` | ✅ 端点正常 |
| 提交订单 | `mtop.trade.order.create.h5` | 4.0 | 未探测 | ❓ 用户暂不需要 |

**探测失败的猜测端点（均返回 `API不存在`）：**
- `mtop.damai.item.subpage.getdetail` ❌
- `mtop.damai.item.sku.getdetail` ❌
- `mtop.damai.item.perform.getdetail` ❌
- `mtop.damai.item.detail.getskudetail` ❌
- `mtop.damai.item.detail.getsubpagedetail` ❌

---

## 三、get_ticket_list（票档列表）— ✅ 已更新

### 3.1 调研结论

通过分析 6 个开源项目（ff522/dm-ticket、ThinkerWen/TicketMonitoring、Chandler0303/python、404fix.cn 等），确认：

- **data body 格式不变**：仍使用 `bizCode/scenario/exParams`（各来源一致）
- **`type=originaljson` 不变**（与 getdetail 不同）
- **URL query params 需更新**：移除 `AntiFlood/method/tb_eagleeyex_scm_project`，新增 `forceAntiCreep/timeout/valueType`

### 3.2 已完成的更新

**文件：** `main.rs:get_ticket_list_res` 函数

URL query params 变更：
```diff
- AntiFlood=true, method=GET, tb_eagleeyex_scm_project=20190509-aone2-join-test
+ forceAntiCreep=true, timeout=10000, valueType=original
```

data body **保持不变**：
```json
{
  "itemId": "xxx",
  "bizCode": "ali.china.damai",
  "scenario": "itemsku",
  "exParams": "{\"dataType\":2,\"dataId\":\"<场次ID>\",\"privilegeActId\":\"\"}",
  "dmChannel": "damai@damaih5_h5"
}
```

---

## 四、其他差异处理状态

### 4.1 User-Agent — ✅ 已更新

Chrome/113 → Chrome/146（2026 年 3 月最新稳定版）：

```diff
- Chrome/113.0.0.0 Mobile Safari/537.36
- sec-ch-ua: "Google Chrome";v="113"
+ Chrome/146.0.0.0 Mobile Safari/537.36
+ sec-ch-ua: "Google Chrome";v="146"
```

同时更新了 Android 设备标识：`Nexus 5 Build/MRA58N` → `Android 10; K`（通用格式）

**修改位置：** `dm_config.rs:USER_AGENT` 和 `SEC_CH_UA`

### 4.2 Baxia SDK — ✅ 已对齐线上

通过抓取大麦 H5 页面源码确认：

**线上实际行为：**
- 只加载一个入口脚本：`//g.alicdn.com/??/AWSC/AWSC/awsc.js,/sd/baxia-entry/baxiaCommon.js`
- **不加载**带版本号的 `baxia/2.5.0/baxiaCommon.js`
- checkApiPath 只检查 `mtop.damai.item.detail.getdetail`（商品详情），不检查订单接口
- init 包含 `paramsType: ["uab","umid","et"]`、`appendTo: "header"`、`showCallback`、`hideCallback`

**已完成的修改：**
- 移除 `BAXIA_VERSIONED_URL`，`loadBaxiaScript()` 改为只加载一个脚本
- `BAXIA_CHECK_API_PATHS` 更新为 `["mtop.damai.item.detail.getdetail"]`
- `initBaxia()` 补全 `paramsType`/`appendTo`/`showCallback`/`hideCallback` 参数

### 4.4 订单端点 URL params — ⚠️ 低优先级

`order.build.h5` 和 `order.create.h5` 仍使用旧风格 params（`AntiFlood/method/tb_eagleeyex_scm_project`）。
探测显示端点正常（返回"Session过期"），暂不改动，待实际测试中如遇问题再更新。

---

## 五、维护速查表

大麦更新后快速排查指南：

| 症状 | 检查文件 | 修改字段 |
|------|----------|----------|
| 签名验证失败 | `dm-config.js` | `DM_APP_KEY` |
| 凭证脚本加载失败 | `dm-config.js` | `BAXIA_ENTRY_URL` |
| 接口 404 / 版本错误 | `dm_config.rs` | `API_VERSION_*` 或 `JSV` |
| User-Agent 被风控 | `dm_config.rs` | `USER_AGENT` / `SEC_CH_UA` |
| 订单参数字段缺失 | `dm-config.js` | `ORDER_TAG_LIST` / `ORDER_HIERARCHY_LIST` |
| Cookie token 提取为空 | `dm-config.js` | `DM_TOKEN_COOKIE_KEY` |
| 商品详情无数据 | `main.rs:get_info` | data body 字段 |
| 票档列表无数据 | `main.rs:get_ticket_list_res` | data body 字段 |
| Baxia 风控路径不匹配 | `dm-config.js` | `BAXIA_CHECK_API_PATHS` |

---

## 六、参考资源

- [GitHub: ff522/dm-ticket (Rust, 1.6k forks)](https://github.com/ff522/dm-ticket) — 最活跃的 Tauri 抢票项目
- [GitHub: ThinkerWen/TicketMonitoring (微信小程序端)](https://github.com/ThinkerWen/TicketMonitoring) — 新版 API 格式参考
- [GitHub: Chandler0303/python damai.py (2025.03)](https://github.com/Chandler0303/python/blob/main/damai.py)
- [CSDN: 演唱会门票解析 subpage.getdetail](https://blog.csdn.net/2301_80446338/article/details/134276070)
- [GitHub: damai_requests (H5/小程序抢票)](https://github.com/gxh27954/damai_requests)
- [GitHub: damai-tickets 抢票脚本](https://github.com/Jxpro/damai-tickets)
- [大麦回流票监控](https://www.404fix.cn/posts/damai-resale-ticket-monitor/)
- [GitHub: oceanzhang01/damaiapi (MtopRequest)](https://github.com/oceanzhang01/damaiapi/blob/master/MtopRequest.java)
