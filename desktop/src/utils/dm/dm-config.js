// ============================================================
// 大麦平台参数配置
// 若大麦更新导致抢票失败，首先检查并更新此文件中的对应参数
// ============================================================

// ---- 签名相关 ----
// 签名算法的 appKey，对应 mtop 接口鉴权
// 若收到"签名错误"类报错，更新此值
export const DM_APP_KEY = "12574478";

// Cookie 中 token 字段名，用于提取签名 token
// 若 getToken() 返回空字符串，检查此字段名
export const DM_TOKEN_COOKIE_KEY = "_m_h5_tk";

// ---- Baxia SDK 相关 ----
// baxia 入口地址（与大麦线上一致，只加载这一个脚本）
// 若凭证脚本加载失败，检查此 URL 是否仍可访问
export const BAXIA_ENTRY_URL =
    "https://g.alicdn.com/??/AWSC/AWSC/awsc.js,/sd/baxia-entry/baxiaCommon.js";

// baxia 初始化等待时间（毫秒）
export const BAXIA_INIT_DELAY_MS = 2000;

// ---- 订单参数字段名 ----
// data 块中需提取的 tag 列表，若订单参数组装失败，检查此列表
export const ORDER_TAG_LIST = [
    "dmPayType",
    "dmEttributesHiddenBlock",
    "dmContactEmail",
    "dmViewer",
    "dmDeliverySelectCard",
    "dmContactPhone",
    "confirmOrder",
    "dmDeliveryAddress",
    "dmContactName",
    "item",
];

// hierarchy 块中需提取的 block key 前缀列表
export const ORDER_HIERARCHY_LIST = [
    "dmPayDetailPopupWindowBlock_",
    "dmViewerBlock_DmViewerBlock",
    "dmContactBlock_DmContactBlock",
    "dmItemBlock_DmItemBlock",
    "dmDeliveryWayBlock_DmDeliveryWayBlock",
    "deliveryMethodOptions_",
    "confirmOrder_1",
    "dmOrderSubmitBlock_DmOrderSubmitBlock",
    "order_",
    "dmPayTypeBlock_DmPayTypeBlock",
    "dmTopNotificationBlock_DmTopNotificationBlock",
];

// 订单渠道标识
export const DM_SUB_CHANNEL = "damai@damaih5_h5";

// ---- 已知错误响应关键词 ----
// 用于识别"有未支付订单"状态，停止抢票
export const MSG_HAVE_ORDER = "您还有未支付订单";
// 用于识别"触发人机验证"状态，停止抢票
export const MSG_VALIDATE = "FAIL_SYS_USER_VALIDATE";
// 用于识别"token 过期"状态
export const MSG_TOKEN_EXPIRED = "令牌过期";

// ---- Baxia 风控路径匹配 ----
// baxia initBaxia() 中 checkApiPath 检查的 API 列表
// 与大麦线上 H5 页面保持一致
export const BAXIA_CHECK_API_PATHS = [
    "mtop.damai.item.detail.getdetail",
];
