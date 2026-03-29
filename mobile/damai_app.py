# -*- coding: UTF-8 -*-
"""
__Author__ = "BlueCestbon"
__Version__ = "2.0.0"
__Description__ = "大麦app抢票自动化 - 优化版"
__Created__ = 2025/09/13 19:27
"""

import time
from datetime import datetime, timezone, timedelta

from appium import webdriver
from appium.options.common.base import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

try:
    from mobile.config import Config
except ImportError:
    from config import Config

try:
    from mobile.logger import get_logger
except ImportError:
    from logger import get_logger

logger = get_logger(__name__)


class DamaiBot:
    def __init__(self):
        self.config = Config.load_config()
        self.driver = None
        self.wait = None
        self._setup_driver()

    def _build_capabilities(self):
        """根据配置构造 Appium capabilities。"""
        capabilities = {
            "platformName": "Android",  # 操作系统
            "deviceName": self.config.device_name,  # 模拟器或真机名称
            "appPackage": self.config.app_package,  # app 包名
            "appActivity": self.config.app_activity,  # app 启动 Activity
            "unicodeKeyboard": True,  # 支持 Unicode 输入
            "resetKeyboard": True,  # 隐藏键盘
            "noReset": True,  # 不重置 app
            "newCommandTimeout": 6000,  # 超时时间
            "automationName": "UiAutomator2",  # 使用 uiautomator2
            "skipServerInstallation": False,  # 跳过服务器安装
            "ignoreHiddenApiPolicyError": True,  # 忽略隐藏 API 策略错误
            "disableWindowAnimation": True,  # 禁用窗口动画
            # 优化性能配置
            "mjpegServerFramerate": 1,  # 降低截图帧率
            "shouldTerminateApp": False,
            "adbExecTimeout": 20000,
        }

        if self.config.udid:
            capabilities["udid"] = self.config.udid

        if self.config.platform_version:
            capabilities["platformVersion"] = self.config.platform_version

        return capabilities

    def _setup_driver(self):
        """初始化驱动配置"""
        device_app_info = AppiumOptions()
        device_app_info.load_capabilities(self._build_capabilities())
        self.driver = webdriver.Remote(self.config.server_url, options=device_app_info)

        # 更激进的性能优化设置
        self.driver.update_settings({
            "waitForIdleTimeout": 0,  # 空闲时间，0 表示不等待，让 UIAutomator2 不等页面“空闲”再返回
            "actionAcknowledgmentTimeout": 0,  # 禁止等待动作确认
            "keyInjectionDelay": 0,  # 禁止输入延迟
            "waitForSelectorTimeout": 300,  # 从500减少到300ms
            "ignoreUnimportantViews": False,  # 保持false避免元素丢失
            "allowInvisibleElements": True,
            "enableNotificationListener": False,  # 禁用通知监听
        })

        # 极短的显式等待，抢票场景下速度优先
        self.wait = WebDriverWait(self.driver, 2)  # 从5秒减少到2秒

    def ultra_fast_click(self, by, value, timeout=1.5):
        """超快速点击 - 适合抢票场景"""
        try:
            # 直接查找并点击，不等待可点击状态
            el = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, value))
            )
            # 使用坐标点击更快
            rect = el.rect
            x = rect['x'] + rect['width'] // 2
            y = rect['y'] + rect['height'] // 2
            self.driver.execute_script("mobile: clickGesture", {
                "x": x,
                "y": y,
                "duration": 50  # 极短点击时间
            })
            return True
        except TimeoutException:
            return False

    def batch_click(self, elements_info, delay=0.1):
        """批量点击操作"""
        for by, value in elements_info:
            if self.ultra_fast_click(by, value):
                if delay > 0:
                    time.sleep(delay)
            else:
                logger.warning(f"点击失败: {value}")

    def ultra_batch_click(self, elements_info, timeout=2):
        """超快批量点击 - 带等待机制"""
        coordinates = []
        # 批量收集坐标，带超时等待
        for by, value in elements_info:
            try:
                # 等待元素出现
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by, value))
                )
                rect = el.rect
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                coordinates.append((x, y, value))
            except TimeoutException:
                logger.warning(f"超时未找到用户: {value}")
            except Exception as e:
                logger.error(f"查找用户失败 {value}: {e}")
        logger.info(f"成功找到 {len(coordinates)} 个用户")
        # 快速连续点击
        for i, (x, y, value) in enumerate(coordinates):
            self.driver.execute_script("mobile: clickGesture", {
                "x": x,
                "y": y,
                "duration": 30
            })
            if i < len(coordinates) - 1:
                time.sleep(0.01)
            logger.debug(f"点击用户: {value}")

    def smart_wait_and_click(self, by, value, backup_selectors=None, timeout=1.5):
        """智能等待和点击 - 支持备用选择器"""
        selectors = [(by, value)]
        if backup_selectors:
            selectors.extend(backup_selectors)

        for selector_by, selector_value in selectors:
            try:
                el = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((selector_by, selector_value))
                )
                rect = el.rect
                x = rect['x'] + rect['width'] // 2
                y = rect['y'] + rect['height'] // 2
                self.driver.execute_script("mobile: clickGesture", {"x": x, "y": y, "duration": 50})
                return True
            except TimeoutException:
                continue
        return False

    def smart_wait_for_element(self, by, value, backup_selectors=None, timeout=1.5):
        """智能等待元素出现 - 支持备用选择器，但不执行点击。"""
        selectors = [(by, value)]
        if backup_selectors:
            selectors.extend(backup_selectors)

        for selector_by, selector_value in selectors:
            try:
                WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((selector_by, selector_value))
                )
                return True
            except TimeoutException:
                continue
        return False

    def wait_for_page_state(self, expected_states, timeout=5, poll_interval=0.2):
        """轮询等待页面进入指定状态，返回最后一次探测结果。"""
        deadline = time.time() + timeout
        last_probe = None

        while time.time() < deadline:
            last_probe = self.probe_current_page()
            if last_probe["state"] in expected_states:
                return last_probe
            time.sleep(poll_interval)

        return last_probe if last_probe is not None else self.probe_current_page()

    def _has_element(self, by, value):
        """快速判断元素是否存在，不等待点击状态。"""
        try:
            return len(self.driver.find_elements(by=by, value=value)) > 0
        except Exception:
            return False

    def _get_current_activity(self):
        """获取当前 Activity，失败时返回空字符串。"""
        try:
            return self.driver.current_activity or ""
        except Exception:
            return ""

    def select_performance_date(self):
        """选择演出场次日期"""
        if not self.config.date:
            return

        date_selector = f'new UiSelector().textContains("{self.config.date}")'
        if self.ultra_fast_click(AppiumBy.ANDROID_UIAUTOMATOR, date_selector, timeout=1.0):
            logger.info(f"选择场次日期: {self.config.date}")
        else:
            logger.debug(f"未找到日期 '{self.config.date}'，使用默认场次")

    def check_session_valid(self):
        """检查大麦 App 登录状态是否有效"""
        activity = self._get_current_activity()
        if "LoginActivity" in activity or "SignActivity" in activity:
            logger.error("检测到登录页面，大麦 App 登录已过期，请重新登录")
            return False

        login_prompt_selectors = [
            'new UiSelector().textContains("请先登录")',
            'new UiSelector().textContains("登录/注册")',
        ]
        for selector in login_prompt_selectors:
            if self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, selector):
                logger.error("检测到登录提示，请重新登录大麦 App")
                return False

        return True

    def wait_for_sale_start(self):
        """等待开售时间，在开售前 countdown_lead_ms 毫秒开始轮询。"""
        if self.config.sell_start_time is None:
            return

        _tz_shanghai = timezone(timedelta(hours=8))
        sell_time = datetime.fromisoformat(self.config.sell_start_time)
        # Ensure timezone-aware
        if sell_time.tzinfo is None:
            sell_time = sell_time.replace(tzinfo=_tz_shanghai)

        now = datetime.now(tz=_tz_shanghai)
        if now >= sell_time:
            logger.info("开售时间已过，跳过等待")
            return

        lead_delta = timedelta(milliseconds=self.config.countdown_lead_ms)
        poll_start = sell_time - lead_delta
        sleep_seconds = (poll_start - now).total_seconds()

        if sleep_seconds > 0:
            logger.info(
                f"等待开售，将在 {self.config.sell_start_time} 前 "
                f"{self.config.countdown_lead_ms}ms 开始轮询"
            )
            time.sleep(sleep_seconds)

        # Tight polling loop (~200ms) until button becomes actionable or timeout
        deadline = sell_time + timedelta(seconds=5)
        while datetime.now(tz=_tz_shanghai) < deadline:
            if self._has_element(
                AppiumBy.ANDROID_UIAUTOMATOR,
                'new UiSelector().textMatches(".*立即.*|.*购买.*|.*选座.*")'
            ):
                logger.info("检测到可购买按钮，开售已开始")
                return
            time.sleep(0.2)

        logger.warning("等待开售超时，继续执行")

    def verify_order_result(self, timeout=5):
        """验证订单提交结果"""
        start = time.time()
        while time.time() - start < timeout:
            activity = self._get_current_activity()

            # Success: payment page
            if any(kw in activity for kw in ("Pay", "Cashier", "AlipayClient")):
                logger.info("订单提交成功，已跳转支付页面")
                return "success"

            # Check page text for various outcomes
            if self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("支付")'):
                logger.info("订单提交成功，检测到支付页面")
                return "success"
            if self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("已售罄")') or \
               self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("库存不足")') or \
               self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("暂时无票")'):
                logger.warning("票已售罄")
                return "sold_out"
            if self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("滑块")') or \
               self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("验证")'):
                logger.warning("触发验证码")
                return "captcha"
            if self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textContains("未支付")'):
                logger.warning("已有未支付订单")
                return "existing_order"

            time.sleep(0.3)

        logger.warning("订单验证超时")
        return "timeout"

    def _fast_retry_from_current_state(self):
        """根据当前页面状态进行快速重试。"""
        page_probe = self.probe_current_page()
        state = page_probe["state"]

        if state in ("detail_page", "sku_page"):
            return self.run_ticket_grabbing()
        elif state == "order_confirm_page":
            submit_selectors = [
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*提交.*|.*确认.*")'),
                (By.XPATH, '//*[contains(@text,"提交")]')
            ]
            return self.smart_wait_and_click(*submit_selectors[0], submit_selectors[1:])
        else:
            self.driver.press_keycode(4)  # Android Back
            time.sleep(0.5)
            return self.run_ticket_grabbing()

    def dismiss_startup_popups(self):
        """处理首启的一次性系统/应用弹窗。"""
        dismissed = False

        popup_clicks = [
            (By.ID, "android:id/ok"),  # Android 全屏提示
            (By.ID, "cn.damai:id/id_boot_action_agree"),  # 大麦隐私协议
            (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("Cancel")'),  # Add to home screen
        ]

        for by, value in popup_clicks:
            if self._has_element(by, value):
                if self.ultra_fast_click(by, value):
                    dismissed = True
                    time.sleep(0.3)

        return dismissed

    def probe_current_page(self):
        """探测当前页面状态和关键控件可见性。"""
        state = "unknown"
        current_activity = self._get_current_activity()
        purchase_button = self._has_element(By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl")
        detail_price_summary = self._has_element(By.ID, "cn.damai:id/project_detail_price_layout")
        sku_price_container = self._has_element(By.ID, "cn.damai:id/project_detail_perform_price_flowlayout")
        quantity_picker = self._has_element(By.ID, "layout_num")
        submit_button = self._has_element(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")')

        if self._has_element(By.ID, "cn.damai:id/id_boot_action_agree"):
            state = "consent_dialog"
        elif self._has_element(By.ID, "cn.damai:id/homepage_header_search"):
            state = "homepage"
        elif "SearchActivity" in current_activity:
            state = "search_page"
        elif submit_button:
            state = "order_confirm_page"
        elif "NcovSkuActivity" in current_activity or \
                self._has_element(By.ID, "cn.damai:id/layout_sku") or \
                self._has_element(By.ID, "cn.damai:id/sku_contanier"):
            state = "sku_page"
        elif "ProjectDetailActivity" in current_activity or purchase_button or detail_price_summary:
            state = "detail_page"

        result = {
            "state": state,
            "purchase_button": purchase_button,
            "price_container": sku_price_container or detail_price_summary,
            "quantity_picker": quantity_picker,
            "submit_button": submit_button,
        }

        logger.info(f"当前页面状态: {result['state']}")
        if current_activity:
            logger.debug(f"当前 Activity: {current_activity}")
        logger.debug(
            "探测结果: "
            f"purchase_button={result['purchase_button']}, "
            f"price_container={result['price_container']}, "
            f"quantity_picker={result['quantity_picker']}, "
            f"submit_button={result['submit_button']}"
        )

        return result

    def run_ticket_grabbing(self):
        """执行抢票主流程"""
        try:
            logger.info("开始抢票流程...")
            start_time = time.time()

            self.dismiss_startup_popups()

            if not self.check_session_valid():
                return False

            page_probe = self.probe_current_page()

            if page_probe["state"] not in {"detail_page", "sku_page"}:
                logger.warning("当前不在演出详情页，请先手动打开目标演出详情页")
                return False

            if self.config.probe_only:
                detail_ready = page_probe["state"] == "detail_page" and page_probe["purchase_button"] and page_probe["price_container"]
                sku_ready = page_probe["state"] == "sku_page" and page_probe["price_container"]

                if detail_ready or sku_ready:
                    logger.info("probe_only 模式: 详情页关键控件已就绪，停止在购票点击前")
                    end_time = time.time()
                    logger.info(f"探测完成，耗时: {end_time - start_time:.2f}秒")
                    return True

                logger.warning("probe_only 模式: 详情页关键控件未就绪")
                return False

            # Wait for sale start if configured
            self.wait_for_sale_start()

            if page_probe["state"] == "detail_page":
                # 0. 选择场次日期（在城市选择前）
                self.select_performance_date()

                # 1. 城市选择 - 准备多个备选方案
                logger.info("选择城市...")
                city_selectors = [
                    (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{self.config.city}")'),
                    (AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().textContains("{self.config.city}")'),
                    (By.XPATH, f'//*[@text="{self.config.city}"]')
                ]
                if not self.smart_wait_and_click(*city_selectors[0], city_selectors[1:]):
                    logger.warning("城市选择失败")
                    return False

                # 2. 点击预约按钮 - 多种可能的按钮文本
                logger.info("点击预约按钮...")
                book_selectors = [
                    (By.ID, "cn.damai:id/trade_project_detail_purchase_status_bar_container_fl"),
                    (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*预约.*|.*购买.*|.*立即.*")'),
                    (By.XPATH, '//*[contains(@text,"预约") or contains(@text,"购买")]')
                ]
                if not self.smart_wait_and_click(*book_selectors[0], book_selectors[1:]):
                    logger.warning("预约按钮点击失败")
                    return False
            else:
                logger.info("当前已在票档选择页，跳过城市和预约按钮步骤")

            # 3. 票价选择 - 优化查找逻辑
            logger.info("选择票价...")
            # Try text-based price matching first
            try:
                price_text_selector = f'new UiSelector().textContains("{self.config.price}")'
                if self.ultra_fast_click(AppiumBy.ANDROID_UIAUTOMATOR, price_text_selector, timeout=1.0):
                    logger.info(f"通过文本匹配选择票价: {self.config.price}")
                else:
                    raise Exception("text match failed")
            except Exception:
                # Fall back to index-based selection (existing code)
                logger.info(f"文本匹配失败，使用索引选择票价: price_index={self.config.price_index}")
                try:
                    price_container = self.driver.find_element(By.ID, 'cn.damai:id/project_detail_perform_price_flowlayout')
                    target_price = price_container.find_element(
                        AppiumBy.ANDROID_UIAUTOMATOR,
                        f'new UiSelector().className("android.widget.FrameLayout").index({self.config.price_index}).clickable(true)'
                    )
                    self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})
                except Exception as e:
                    logger.warning(f"票价选择失败，启动备用方案: {e}")
                    price_container = self.wait.until(
                        EC.presence_of_element_located((By.ID, 'cn.damai:id/project_detail_perform_price_flowlayout')))
                    target_price = price_container.find_element(
                        AppiumBy.ANDROID_UIAUTOMATOR,
                        f'new UiSelector().className("android.widget.FrameLayout").index({self.config.price_index}).clickable(true)'
                    )
                    self.driver.execute_script('mobile: clickGesture', {'elementId': target_price.id})

            # 4. 数量选择
            logger.info("选择数量...")
            if self.driver.find_elements(by=By.ID, value='layout_num'):
                clicks_needed = len(self.config.users) - 1
                if clicks_needed > 0:
                    try:
                        plus_button = self.driver.find_element(By.ID, 'img_jia')
                        for i in range(clicks_needed):
                            rect = plus_button.rect
                            x = rect['x'] + rect['width'] // 2
                            y = rect['y'] + rect['height'] // 2
                            self.driver.execute_script("mobile: clickGesture", {
                                "x": x,
                                "y": y,
                                "duration": 50
                            })
                            time.sleep(0.02)
                    except Exception as e:
                        logger.error(f"快速点击加号失败: {e}")

            # if self.driver.find_elements(by=By.ID, value='layout_num') and self.config.users is not None:
            #     for i in range(len(self.config.users) - 1):
            #         self.driver.find_element(by=By.ID, value='img_jia').click()

            # 5. 确定购买
            logger.info("确定购买...")
            if not self.ultra_fast_click(By.ID, "btn_buy_view"):
                # 备用按钮文本
                self.ultra_fast_click(AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*确定.*|.*购买.*")')

            post_buy_probe = self.wait_for_page_state({"order_confirm_page"}, timeout=5)
            if post_buy_probe["state"] != "order_confirm_page":
                # 6. 批量选择用户
                logger.info("选择用户...")
                user_clicks = [(AppiumBy.ANDROID_UIAUTOMATOR, f'new UiSelector().text("{user}")') for user in
                               self.config.users]
                # self.batch_click(user_clicks, delay=0.05)  # 极短延迟
                self.ultra_batch_click(user_clicks)
                post_buy_probe = self.wait_for_page_state({"order_confirm_page"}, timeout=5)

            if post_buy_probe["state"] != "order_confirm_page":
                logger.warning("未进入订单确认页，请检查票档可用性或观演人配置")
                return False

            submit_selectors = [
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().text("立即提交")'),
                (AppiumBy.ANDROID_UIAUTOMATOR, 'new UiSelector().textMatches(".*提交.*|.*确认.*")'),
                (By.XPATH, '//*[contains(@text,"提交")]')
            ]
            if not self.config.if_commit_order:
                logger.info("if_commit_order=False，等待确认页就绪后停止在提交订单前")
                if not self.smart_wait_for_element(*submit_selectors[0], submit_selectors[1:]):
                    logger.warning("确认页提交按钮未找到，请手动确认是否已到订单确认页")
                    return False

                end_time = time.time()
                logger.info(f"已到订单确认页，未提交订单，耗时: {end_time - start_time:.2f}秒")
                return True

            # 7. 提交订单
            logger.info("提交订单...")
            submit_success = self.smart_wait_and_click(*submit_selectors[0], submit_selectors[1:])
            if not submit_success:
                logger.warning("提交订单按钮未找到，请手动确认订单状态")

            # 8. 验证订单结果
            result = self.verify_order_result()
            if result == "success":
                end_time = time.time()
                logger.info(f"抢票成功！耗时: {end_time - start_time:.2f}秒")
                return True
            elif result in ("sold_out", "captcha", "existing_order"):
                return False
            # timeout/unknown — optimistically return True (submit may have worked)
            end_time = time.time()
            logger.info(f"抢票流程完成，耗时: {end_time - start_time:.2f}秒")
            return True

        except Exception as e:
            logger.error(f"抢票过程发生错误: {e}")
            return False
        finally:
            time.sleep(1)  # 给最后的操作一点时间

    def run_with_retry(self, max_retries=3):
        """带重试机制的抢票"""
        for attempt in range(max_retries):
            logger.info(f"第 {attempt + 1} 次尝试...")
            if self.run_ticket_grabbing():
                logger.info("抢票成功！")
                return True

            # Fast retry within same session
            for fast_attempt in range(self.config.fast_retry_count):
                logger.info(f"快速重试 {fast_attempt + 1}/{self.config.fast_retry_count}...")
                time.sleep(self.config.fast_retry_interval_ms / 1000)
                if self._fast_retry_from_current_state():
                    logger.info("快速重试成功！")
                    return True

            # Full driver recreation
            logger.warning(f"第 {attempt + 1} 次尝试及快速重试均失败")
            if attempt < max_retries - 1:
                logger.info("重建驱动后重试...")
                try:
                    self.driver.quit()
                except Exception:
                    pass
                self._setup_driver()

        logger.error("所有尝试均失败")
        return False


# 使用示例
if __name__ == "__main__":
    bot = DamaiBot()
    try:
        bot.run_with_retry(max_retries=3)
    finally:
        try:
            bot.driver.quit()
        except Exception:
            pass
