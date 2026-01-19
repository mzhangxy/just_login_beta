import os
import time
import json
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException

# 日志配置 - 更详细
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

# Cookies 文件路径（假设在仓库根目录，可在 Actions 中 git add/commit/push）
COOKIES_FILE = 'cookies.json'

class JustRunMyAppLoginBot:
    def __init__(self):
        self.email = os.getenv("USER_EMAIL")
        self.password = os.getenv("USER_PASSWORD")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY")
        self.app_id = "2126"
        
        if not all([self.email, self.password, self.api_key]):
            raise ValueError("缺少环境变量: USER_EMAIL / USER_PASSWORD / TWOCAPTCHA_API_KEY")
        
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._init_driver()
        self.wait = WebDriverWait(self.driver, 45)
        self.saved_cookies = self._load_saved_cookies()  # 预加载保存的 cookies

    def _init_driver(self):
        options = uc.ChromeOptions()
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_argument('--window-size=1920,1080')
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("运行在 GitHub Actions，使用 headless=new")
            options.add_argument('--headless=new')
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')
        
        driver = uc.Chrome(options=options)
        
        driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": "Object.defineProperty(navigator, 'webdriver', {get: () => undefined});"
        })
        
        return driver

    def _load_saved_cookies(self):
        """加载保存的 cookies 文件"""
        if os.path.exists(COOKIES_FILE):
            try:
                with open(COOKIES_FILE, 'r') as f:
                    cookies = json.load(f)
                logger.info(f"从 {COOKIES_FILE} 加载了 {len(cookies)} 个 cookies")
                return cookies
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {str(e)}")
        else:
            logger.info(f"未找到 {COOKIES_FILE}，将使用账号密码登录")
        return None

    def _save_cookies(self, new_cookies):
        """保存新的 cookies 到文件"""
        try:
            with open(COOKIES_FILE, 'w') as f:
                json.dump(new_cookies, f, indent=4)
            logger.info(f"已更新 cookies 到 {COOKIES_FILE}")
            # 在 GitHub Actions 中，需要额外步骤 commit/push（见 README 说明）
        except Exception as e:
            logger.error(f"保存 cookies 失败: {str(e)}")

    def _cookies_equal(self, cookies1, cookies2):
        """比较两个 cookies 列表是否本质相同（忽略 expires/sameSite 等动态字段，只比 name/value/domain/path）"""
        if not cookies1 or not cookies2:
            return False
        def normalize_cookie(c):
            return {k: v for k, v in c.items() if k in ['name', 'value', 'domain', 'path']}
        
        set1 = {json.dumps(normalize_cookie(c), sort_keys=True) for c in cookies1}
        set2 = {json.dumps(normalize_cookie(c), sort_keys=True) for c in cookies2}
        return set1 == set2

    def login_with_retry(self, max_attempts=3):
        attempt = 1
        while attempt <= max_attempts:
            logger.info(f"===== 登录尝试 {attempt}/{max_attempts} 开始 =====")
            try:
                if self._try_cookie_login():
                    logger.info("Cookie 登录成功")
                else:
                    logger.info("Cookie 登录失败或无 cookies，fallback 到账号密码登录")
                    self._perform_login()
                    logger.info("账号密码登录成功")
                
                # 登录后检查并更新 cookies
                self._check_and_update_cookies()
                
                logger.info("登录流程执行完成，视为成功")
                return True
            except Exception as e:
                logger.error(f"登录尝试 {attempt} 失败: {str(e)}")
                if attempt == max_attempts:
                    raise
                logger.info(f"将在 8~12 秒后进行第 {attempt+1} 次重试...")
                time.sleep(8 + attempt * 2)  # 递增等待
            finally:
                # 无论成功失败都打印当前 url 和 title，便于排查
                try:
                    current_url = self.driver.current_url
                    page_title = self.driver.title
                    logger.info(f"当前页面: {current_url} | 标题: {page_title}")
                except:
                    pass
            attempt += 1
        return False

    def _try_cookie_login(self):
        """尝试使用保存的 cookies 登录"""
        if not self.saved_cookies:
            return False
        
        try:
            # 先访问域名以设置 cookies
            self.driver.get("https://justrunmy.app")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 添加 cookies
            for cookie in self.saved_cookies:
                self.driver.add_cookie(cookie)
            
            # 刷新或直接访问 panel 检查是否登录
            self.driver.get("https://justrunmy.app/panel")
            self.wait.until(EC.url_contains("/panel"))
            
            # 检查是否有 dashboard 元素确认已登录（可根据实际页面调整）
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(),'Dashboard') or contains(text(),'Applications') or @class='sidebar']")
            ))
            
            return True
        except TimeoutException:
            logger.info("Cookie 登录后未跳转到 panel 或缺少关键元素，视为失效")
            return False
        except Exception as e:
            logger.warning(f"Cookie 登录异常: {str(e)}")
            return False

    def _perform_login(self):
        # 1. 访问首页
        logger.info("Step 1: 打开首页")
        self.driver.get("https://justrunmy.app")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        # 处理 Cookies 弹窗
        try:
            accept_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//button[contains(., "Accept") or contains(., "Agree")]')
            ))
            accept_btn.click()
            logger.info("Cookies 已接受")
        except TimeoutException:
            logger.info("未出现 Cookies 弹窗，跳过")

        # 2. 点击 Sign in
        logger.info("Step 2: 点击 Sign in")
        signin_link = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
        signin_link.click()

        # 3. 等待登录页加载（更严格）
        logger.info("Step 3: 等待登录表单出现")
        self.wait.until(EC.presence_of_element_located((By.NAME, "Email")))
        self.wait.until(EC.presence_of_element_located((By.NAME, "Password")))

        # 4. 填写邮箱
        logger.info("Step 4: 填写邮箱")
        email_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Email")))
        self.driver.execute_script("arguments[0].value = arguments[1];", email_field, self.email)

        # 5. 填写密码
        logger.info("Step 5: 填写密码")
        password_field = self.wait.until(EC.visibility_of_element_located((By.NAME, "Password")))
        self.driver.execute_script("arguments[0].value = arguments[1];", password_field, self.password)

        # 6. 处理 Cloudflare Turnstile
        logger.info("Step 6: 处理 CF Turnstile")
        try:
            cf_div = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_div.get_attribute("data-sitekey")
            if sitekey:
                logger.info(f"发现 Turnstile，sitekey: {sitekey}")
                result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                token = result['code']
                self.driver.execute_script(
                    f'document.querySelector("input[name=\'cf-turnstile-response\']").value = "{token}";'
                )
                logger.info("Turnstile token 已注入")
                # 等待 token 被表单识别（部分场景需要）
                time.sleep(1.5)
        except TimeoutException:
            logger.info("本轮未检测到 Turnstile，跳过验证码处理")
        except Exception as e:
            logger.warning(f"Turnstile 处理异常（非致命）: {str(e)}")

        # 7. 提交登录
        logger.info("Step 7: 点击提交按钮")
        submit_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
        self.driver.execute_script("arguments[0].click();", submit_btn)

        # 8. 等待跳转到 panel 页面
        logger.info("Step 8: 等待跳转至 /panel")
        self.wait.until(EC.url_contains("/panel"))
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        logger.info("已进入控制面板")
        self.driver.save_screenshot("debug_5_panel.png")

    def _check_and_update_cookies(self):
        """登录后检查当前 cookies 与保存的是否相同，如果不同则更新"""
        current_cookies = self.driver.get_cookies()
        if not self._cookies_equal(current_cookies, self.saved_cookies):
            logger.info("检测到 cookies 已变更，将更新保存的文件")
            self._save_cookies(current_cookies)
            self.saved_cookies = current_cookies  # 更新内存中的
        else:
            logger.info("cookies 无变更，无需更新")

    def run(self):
        try:
            # 执行带重试的登录
            self.login_with_retry(max_attempts=3)

            # 9. 直接导航至应用详情页
            logger.info(f"Step 9: 导航至应用 {self.app_id} 详情页")
            detail_url = f"https://justrunmy.app/panel/application/{self.app_id}/"
            self.driver.get(detail_url)
            
            # 等待页面主体加载
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            time.sleep(2)  # 保留少量缓冲，等待 JS 渲染
            self.driver.save_screenshot("debug_6_app_detail.png")

            # 10. 检测运行状态并处理启动 ===
            logger.info("Step 10: 检查应用运行状态")

            # 更宽松的 Running 检测（不区分大小写，包含 running/running/等）
            running_indicators = [
                (By.XPATH, "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'running')]"),
                (By.XPATH, "//*[contains(@class, 'status') or contains(@class, 'badge') or contains(@class, 'label')][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'running')]"),
            ]

            is_running = False
            for by, value in running_indicators:
                try:
                    elem = self.wait.until(EC.presence_of_element_located((by, value)))
                    logger.info(f"检测到 Running 状态 (使用选择器: {by} = {value})")
                    is_running = True
                    break
                except TimeoutException:
                    continue

            if not is_running:
                logger.info("未检测到 Running 状态，尝试启动应用...")
                
                # 尝试多种 Start 按钮定位方式（优先级从高到低）
                start_candidates = [
                    (By.XPATH, "//button[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'start')]"),
                    (By.XPATH, "//button[contains(., 'Start') or contains(., 'start')]"),
                    (By.CSS_SELECTOR, "button[class*='start'], button[class*='launch'], button[class*='run']"),
                    (By.XPATH, "//*[contains(@aria-label, 'start') or contains(@title, 'start') or contains(@class, 'start')]//button"),
                ]

                start_btn = None
                for by, value in start_candidates:
                    try:
                        start_btn = self.wait.until(EC.element_to_be_clickable((by, value)))
                        logger.info(f"找到 Start 按钮，使用选择器: {by} = {value}")
                        break
                    except TimeoutException:
                        continue

                if start_btn:
                    self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", start_btn)
                    time.sleep(0.6)
                    self.driver.execute_script("arguments[0].click();", start_btn)
                    logger.info("已点击 Start 按钮")

                    # 等待 Running 出现（最长等待 90 秒）
                    self.wait.until(lambda driver: any(
                        driver.find_elements(By.XPATH, xp) for xp in [
                            "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'running')]",
                            "//*[contains(@class, 'status')][contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'running')]"
                        ]
                    ), message="等待应用启动到 Running 状态超时（90秒）")
                    
                    logger.info("应用已启动，检测到 Running 状态")
                    time.sleep(1.5)  # 轻微缓冲
                    self.driver.save_screenshot("debug_6.5_started.png")
                else:
                    raise Exception("未找到 Start 按钮，且应用不在 Running 状态")

            else:
                logger.info("应用已在 Running 状态，无需启动")

            # 11. 检查并点击 Reset Timer
            logger.info("Step 11: 寻找并点击 Reset Timer")
            reset_xpath = '//button[contains(., "Reset Timer")]'
            
            reset_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, reset_xpath)))
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", reset_btn)
            time.sleep(0.8)
            
            self.driver.execute_script("arguments[0].click();", reset_btn)
            logger.info("已点击 Reset Timer 按钮")
            
            time.sleep(2.5)
            self.driver.save_screenshot("debug_7_done.png")
            logger.info("续费/重置流程完成")

        except Exception as e:
            timestamp = time.strftime("%Y%m%d_%H%M%S")
            try:
                self.driver.save_screenshot(f"error_{timestamp}.png")
            except:
                pass
            logger.error(f"整体流程失败: {str(e)}", exc_info=True)
            raise
        finally:
            try:
                self.driver.quit()
            except:
                pass

if __name__ == "__main__":
    bot = JustRunMyAppLoginBot()
    bot.run()
