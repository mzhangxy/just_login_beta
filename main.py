import os
import time
import logging
import undetected_chromedriver as uc
from twocaptcha import TwoCaptcha
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 日志配置 ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class JustRunMyAppBot:
    def __init__(self):
        self.email = os.getenv("USER_EMAIL")
        self.password = os.getenv("USER_PASSWORD")
        self.api_key = os.getenv("TWOCAPTCHA_API_KEY")
        
        self.solver = TwoCaptcha(self.api_key)
        self.driver = self._setup_driver()
        self.wait = WebDriverWait(self.driver, 35)  # 增加等待时间以应对重定向

    def _setup_driver(self):
        options = uc.ChromeOptions()
        
        # 更强的伪装参数
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        if os.getenv("GITHUB_ACTIONS") == "true":
            logger.info("GitHub 环境，headless + 额外伪装")
            options.add_argument('--headless=new')  # 试试 new headless，更像真实浏览器
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            options.add_argument('--disable-gpu')  # 有时有助于
        
        # 随机化一点 user-agent（需要 pip install fake-useragent）
        try:
            from fake_useragent import UserAgent
            ua = UserAgent()
            options.add_argument(f'--user-agent={ua.random}')
        except ImportError:
            options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
        
        options.add_argument('--window-size=1920,1080')
        
        # 关键：让 browser 像正常用户一样
        driver = uc.Chrome(
            options=options,
            version_main=130,  # 建议锁定一个比较新的稳定版本，根据你的环境调整
            headless=True if os.getenv("GITHUB_ACTIONS") else False
        )
        
        # 额外 JS 隐藏 webdriver 痕迹
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        return driver

    def login(self):
        try:
            logger.info("Step 1: 打开首页")
            self.driver.get("https://justrunmy.app")
            time.sleep(3)  # 给首页一点缓冲
            self.driver.save_screenshot("debug_1_homepage.png")
            logger.info(f"首页标题: {self.driver.title}")
            logger.info(f"首页 URL: {self.driver.current_url}")
            logger.info(f"首页 source 前200字: {self.driver.page_source[:200]}...")

            # Step 2: 找 Sign in 按钮并点击
            logger.info("Step 2: 尝试点击 Sign in")
            try:
                signin_btn = self.wait.until(EC.element_to_be_clickable((By.LINK_TEXT, "Sign in")))
                signin_btn.click()
                logger.info("成功点击 Sign in (用 Link Text)")
            except:
                logger.warning("没找到 Link Text 'Sign in'，尝试 CSS 选择器...")
                signin_btn = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 'a[href*="login"], a[href*="account"], button:contains("Sign in")')))
                signin_btn.click()

            time.sleep(4)
            self.driver.save_screenshot("debug_2_after_click_signin.png")

            # Step 3: 等登录页出现
            logger.info("Step 3: 等待 URL 包含 account/login")
            self.wait.until(EC.url_contains("account/login"))
            logger.info(f"到达登录页 URL: {self.driver.current_url}")

            # 关键诊断点：打印页面源码 + 找所有 input
            time.sleep(5)  # 额外等 SPA/JS 加载
            self.driver.save_screenshot("debug_3_login_page_before_input.png")
            
            page_source = self.driver.page_source.lower()
            logger.info("页面标题: " + self.driver.title)
            
            # 检查是否卡在 Cloudflare
            if "checking your browser" in page_source or "turnstile" in page_source or "cf-browser-verification" in page_source:
                logger.error("!!! 疑似卡在 Cloudflare 验证页面 !!!")
                logger.info("页面源码片段: " + page_source[page_source.find("cf-"):page_source.find("cf-")+500])
            
            # 尝试切换到可能的 iframe
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            logger.info(f"找到 {len(iframes)} 个 iframe")
            form_frame = None
            for idx, iframe in enumerate(iframes):
                try:
                    src = iframe.get_attribute("src") or "(无src)"
                    logger.info(f"iframe {idx+1} src: {src}")
                    self.driver.switch_to.frame(iframe)
                    inputs_in_frame = self.driver.find_elements(By.TAG_NAME, "input")
                    logger.info(f"  → 该 iframe 内有 {len(inputs_in_frame)} 个 input")
                    # 如果有 input，就停留在这里操作
                    if inputs_in_frame:
                        logger.info("找到表单所在的 iframe！后续操作都在这里执行")
                        form_frame = iframe
                        break  # 保持在该 frame 里
                    self.driver.switch_to.default_content()
                except:
                    self.driver.switch_to.default_content()
            
            # 列出所有可见的 input 元素（超级有用！）
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            logger.info(f"页面中共找到 {len(inputs)} 个 <input> 元素")
            for i, inp in enumerate(inputs):
                try:
                    name = inp.get_attribute("name") or "(无name)"
                    typ = inp.get_attribute("type") or "(无type)"
                    id_ = inp.get_attribute("id") or "(无id)"
                    ph = inp.get_attribute("placeholder") or "(无placeholder)"
                    visible = inp.is_displayed()
                    logger.info(f"Input {i+1}: name={name}, type={typ}, id={id_}, placeholder={ph}, visible={visible}")
                except:
                    pass

            # 再检查 cf-turnstile
            try:
                cf_container = self.driver.find_element(By.CLASS_NAME, "cf-turnstile")
                logger.info("找到 cf-turnstile！ sitekey = " + cf_container.get_attribute("data-sitekey"))
                sitekey = cf_container.get_attribute("data-sitekey")
            except:
                logger.warning("没找到 cf-turnstile 容器")
                sitekey = None  # 如果没有，就跳过

            # 如果到这里还有 input，就尝试用最宽松的方式定位邮箱
            if inputs:
                email_input = None
                for selector in [
                    (By.NAME, "Input.Username"),
                    (By.NAME, "email"),
                    (By.NAME, "username"),
                    (By.CSS_SELECTOR, 'input[type="email"], input[placeholder*="mail" i], input[name*="user" i]'),
                    (By.XPATH, '//input[contains(@type,"email") or contains(@name,"user") or contains(@placeholder,"mail")]')
                ]:
                    try:
                        email_input = self.wait.until(EC.visibility_of_element_located(selector))
                        logger.info(f"成功用 {selector} 找到邮箱输入框！")
                        break
                    except:
                        continue
                
                if email_input:
                    self.driver.execute_script("arguments[0].value = arguments[1];", email_input, self.email)
                    logger.info("用户名已注入")
                    
                    # 密码同理
                    password_input = None
                    try:
                        password_input = self.wait.until(EC.visibility_of_element_located((By.CSS_SELECTOR, 'input[type="password"]')))
                        self.driver.execute_script("arguments[0].value = arguments[1];", password_input, self.password)
                        logger.info("密码已注入")
                    except:
                        raise Exception("找不到密码输入框！")
                    
                    # 处理 Cloudflare Turnstile（如果存在）
                    if sitekey:
                        logger.info("正在检测并破解验证码...")
                        result = self.solver.turnstile(sitekey=sitekey, url=self.driver.current_url)
                        token = result['code']
                        
                        # 注入 Token
                        self.driver.execute_script(f'document.getElementsByName("cf-turnstile-response")[0].value="{token}";')
                        logger.info("Token 注入完毕")
                        time.sleep(1.5)  # 让页面校验 token
                    else:
                        logger.info("无 Turnstile，跳过验证码步骤")
                    
                    # 提交表单
                    logger.info("准备提交表单")
                    try:
                        submit_btn = self.driver.find_element(By.CSS_SELECTOR, "button[type='submit'], button:contains('SIGN IN')")
                        self.driver.execute_script("arguments[0].click();", submit_btn)
                    except:
                        raise Exception("找不到提交按钮！")
                    
                    # 最终验证
                    self.wait.until(EC.url_contains("/panel"))
                    logger.info("🎉 登录成功！")
                else:
                    raise Exception("所有尝试定位邮箱输入框都失败了，看上面 input 列表！")
            else:
                raise Exception("页面根本没有 <input> 元素！很可能被 Cloudflare 拦截或页面没加载完")
            
            # 如果在 iframe 中操作完，切换回默认
            if form_frame:
                self.driver.switch_to.default_content()

        except Exception as e:
            self.driver.save_screenshot("error_debug_final.png")
            logger.error(f"❌ 运行失败: {str(e)}")
            logger.info(f"失败时的 URL: {self.driver.current_url}")
            logger.info(f"失败时页面标题: {self.driver.title}")
        finally:
            self.driver.quit()

if __name__ == "__main__":
    bot = JustRunMyAppBot()
    bot.login()
