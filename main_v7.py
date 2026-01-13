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

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s | %(levelname)-7s | %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

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
        self.saved_cookies = self._load_saved_cookies()

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
        if os.path.exists(COOKIES_FILE):
            try:
                with open(COOKIES_FILE, 'r') as f:
                    cookies = json.load(f)
                logger.info(f"从 {COOKIES_FILE} 加载了 {len(cookies)} 个关键 cookies")
                return cookies
            except Exception as e:
                logger.warning(f"加载 cookies 失败: {str(e)}")
        else:
            logger.info(f"未找到 {COOKIES_FILE}，将使用账号密码登录")
        return None

    def _save_cookies(self, new_cookies):
        """优化版：只保存关键的登录 Session、域名相关 Cookie 和 CF 凭证"""
        try:
            allowed_domains = ['justrunmy.app', '.justrunmy.app']
            critical_prefixes = ['cf_']
            filtered_cookies = []
            seen_names = set()

            for cookie in new_cookies:
                name = cookie.get('name', '')
                domain = cookie.get('domain', '')
                is_target_domain = any(domain == d for d in allowed_domains)
                is_cf_cookie = any(name.startswith(p) for p in critical_prefixes)

                if is_target_domain or is_cf_cookie:
                    if name not in seen_names:
                        filtered_cookies.append(cookie)
                        seen_names.add(name)

            with open(COOKIES_FILE, 'w') as f:
                json.dump(filtered_cookies, f, indent=4)
            logger.info(f"已清理并更新 cookies (保留了关键的 {len(filtered_cookies)} 个)")
        except Exception as e:
            logger.error(f"保存 cookies 失败: {str(e)}")

    def _cookies_equal(self, cookies1, cookies2):
        """同步优化版：只对比关键字段，忽略容易变动的动态属性"""
        if not cookies1 or not cookies2:
            return False

        def get_critical_state(cookies):
            allowed_domains = ['justrunmy.app', '.justrunmy.app']
            critical_prefixes = ['cf_']
            critical_data = []
            for c in cookies:
                name = c.get('name', '')
                domain = c.get('domain', '')
                is_target = any(domain == d for d in allowed_domains)
                is_cf = any(name.startswith(p) for p in critical_prefixes)
                if is_target or is_cf:
                    normalized = {
                        'name': name,
                        'value': c.get('value', ''),
                        'domain': domain
                    }
                    critical_data.append(json.dumps(normalized, sort_keys=True))
            return set(critical_data)

        return get_critical_state(cookies1) == get_critical_state(cookies2)

    def _check_and_update_cookies(self):
        current_cookies = self.driver.get_cookies()
        if not self._cookies_equal(current_cookies, self.saved_cookies):
            logger.info("检测到关键登录态已变更，将更新保存的文件")
            self._save_cookies(current_cookies)
            self.saved_cookies = current_cookies
        else:
            logger.info("关键 cookies 无变更，无需更新")

    def login_with_retry(self, max_attempts=3):
        attempt = 1
        while attempt <= max_attempts:
            logger.info(f"===== 登录尝试 {attempt}/{max_attempts} 开始 =====")
            try:
                if self._try_cookie_login():
                    logger.info("Cookie 登录成功")
                else:
                    logger.info("Cookie 登录失败或无有效 cookies，执行账号密码登录")
                    self._perform_login()
                
                self._check_and_update_cookies()
                return True
            except Exception as e:
                logger.error(f"登录尝试 {attempt} 失败: {str(e)}")
                if attempt == max_attempts: raise
                time.sleep(8 + attempt * 2)
            finally:
                try:
                    logger.info(f"当前页面: {self.driver.current_url} | 标题: {self.driver.title}")
                except: pass
            attempt += 1
        return False

    def _try_cookie_login(self):
        if not self.saved_cookies: return False
        try:
            self.driver.get("https://justrunmy.app")
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            for cookie in self.saved_cookies:
                self.driver.add_cookie(cookie)
            self.driver.get("https://justrunmy.app/panel")
            self.wait.until(EC.url_contains("/panel"))
            self.wait.until(EC.presence_of_element_located(
                (By.XPATH, "//*[contains(text(),'Dashboard') or contains(text(),'Applications') or @class='sidebar']")
            ))
            return True
        except:
            return False

    def _perform_login(self):
        logger.info("Step 1: 打开首页")
        self.driver.get("https://justrunmy.app")
        self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))

        try:
            accept_btn = self.wait.until(EC.element_to_be_clickable(
                (By.XPATH, '//button[contains(., "Accept") or contains(., "Agree")]')
            ))
            accept_btn.click()
        except: pass

        logger.info("Step 2: 进入登录页")
        self.driver.get("https://justrunmy.app/login") # 直接跳转登录页更高效
        self.wait.until(EC.presence_of_element_located((By.NAME, "Email")))

        logger.info("Step 4-5: 填写凭据")
        self.driver.execute_script("arguments[0].value = arguments[1];", 
                                   self.wait.until(EC.visibility_of_element_located((By.NAME, "Email"))), self.email)
        self.driver.execute_script("arguments[0].value = arguments[1];", 
                                   self.wait.until(EC.visibility_of_element_located((By.NAME, "Password"))), self.password)

        logger.info("Step 6: 处理 CF Turnstile")
        try:
            cf_div = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "cf-turnstile")))
            sitekey = cf_div.get_attribute("data-sitekey")
            if sitekey:
                result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                self.driver.execute_script(
                    f'document.querySelector("input[name=\'cf-turnstile-response\']").value = "{result["code"]}";'
                )
                time.sleep(1.5)
        except: logger.info("跳过验证码步骤")

        logger.info("Step 7: 提交登录")
        submit_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'button[type="submit"]')))
        self.driver.execute_script("arguments[0].click();", submit_btn)
        self.wait.until(EC.url_contains("/panel"))

    def run(self):
        try:
            self.login_with_retry(max_attempts=3)
            detail_url = f"https://justrunmy.app/panel/application/{self.app_id}/"
            self.driver.get(detail_url)
            self.wait.until(EC.presence_of_element_located((By.TAG_NAME, "body")))
            
            # 检测 Running 状态并处理启动
            is_running = False
            try:
                self.wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(translate(text(), 'ABC', 'abc'), 'running')]")))
                is_running = True
                logger.info("应用已在 Running 状态")
            except: pass

            if not is_running:
                start_btn = self.wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Start') or contains(., 'start')]")))
                self.driver.execute_script("arguments[0].click();", start_btn)
                logger.info("已点击 Start 按钮")
                time.sleep(5)

            # 点击 Reset Timer
            reset_btn = self.wait.until(EC.presence_of_element_located((By.XPATH, '//button[contains(., "Reset Timer")]')))
            self.driver.execute_script("arguments[0].click();", reset_btn)
            logger.info("续费/重置流程完成")
            time.sleep(2.5)

        except Exception as e:
            try: self.driver.save_screenshot(f"error_{time.strftime('%Y%m%d_%H%M%S')}.png")
            except: pass
            logger.error(f"整体流程失败: {str(e)}", exc_info=True)
            raise
        finally:
            self.driver.quit()

if __name__ == "__main__":
    JustRunMyAppLoginBot().run()
