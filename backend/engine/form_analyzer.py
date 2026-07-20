"""
AI钓鱼网站检测后端 - 表单分析器
解析HTML页面中的<form>元素，检测是否存在敏感字段及可疑提交行为
"""

import re
import logging
from bs4 import BeautifulSoup
from urllib.parse import urlparse, urljoin

from ..utils.config import Config

logger = logging.getLogger(__name__)


class FormAnalyzer:
    """表单分析器：解析HTML内容中的表单元素，检测敏感输入字段和可疑action。

    钓鱼网站通常会包含要求用户输入密码、信用卡号、身份证号等敏感信息的表单。
    此外，表单action指向外部域名也是常见钓鱼特征。
    """

    # 敏感字段关键词列表
    SENSITIVE_FIELDS = Config.SENSITIVE_FORM_FIELDS

    def __init__(self):
        """初始化表单分析器"""
        pass

    # ==================== 敏感字段检测 ====================

    def analyze_form_fields(self, html_content: str) -> dict:
        """解析HTML中的所有表单，检测是否存在敏感输入字段。

        检测依据：input元素的 name/id/placeholder/type 属性中
        是否包含敏感关键词（password/card/ssn/身份证等）。

        Args:
            html_content: 页面HTML内容字符串

        Returns:
            dict: {
                "has_sensitive_fields": bool,        # 是否存在敏感字段
                "sensitive_field_types": list[str],  # 检测到的敏感字段类型列表
                "form_count": int,                   # 表单总数
                "input_count": int,                  # 所有input元素总数
                "sensitive_input_details": list[dict], # 敏感input的详细信息
            }
        """
        if not html_content:
            return self._empty_field_result()

        try:
            soup = BeautifulSoup(html_content, "html.parser")
        except Exception as e:
            logger.error(f"HTML解析失败: {e}")
            return self._empty_field_result()

        # 查找所有form元素
        forms = soup.find_all("form")
        form_count = len(forms)

        # 查找所有input元素
        all_inputs = soup.find_all("input")
        input_count = len(all_inputs)

        sensitive_field_types = set()
        sensitive_input_details = []

        for input_elem in all_inputs:
            # 收集input元素的属性用于匹配
            name = (input_elem.get("name") or "").lower()
            input_id = (input_elem.get("id") or "").lower()
            placeholder = (input_elem.get("placeholder") or "").lower()
            input_type = (input_elem.get("type") or "").lower()
            autocomplete = (input_elem.get("autocomplete") or "").lower()

            # 合并所有可检测文本
            combined_text = f"{name} {input_id} {placeholder} {input_type} {autocomplete}"

            # 检测敏感关键词
            matched_keywords = []
            for keyword in self.SENSITIVE_FIELDS:
                if keyword in combined_text:
                    matched_keywords.append(keyword)
                    sensitive_field_types.add(keyword)

            if matched_keywords:
                sensitive_input_details.append({
                    "name": input_elem.get("name", ""),
                    "id": input_elem.get("id", ""),
                    "type": input_elem.get("type", ""),
                    "placeholder": input_elem.get("placeholder", ""),
                    "matched_keywords": matched_keywords,
                })

        has_sensitive = len(sensitive_field_types) > 0

        logger.info(
            f"表单分析完成: forms={form_count}, inputs={input_count}, "
            f"sensitive_types={list(sensitive_field_types)}"
        )

        return {
            "has_sensitive_fields": has_sensitive,
            "sensitive_field_types": list(sensitive_field_types),
            "form_count": form_count,
            "input_count": input_count,
            "sensitive_input_details": sensitive_input_details,
        }

    @staticmethod
    def _empty_field_result() -> dict:
        """返回空的表单分析结果"""
        return {
            "has_sensitive_fields": False,
            "sensitive_field_types": [],
            "form_count": 0,
            "input_count": 0,
            "sensitive_input_details": [],
        }

    # ==================== 表单action分析 ====================

    def analyze_form_action(self, form_action: str, page_domain: str) -> dict:
        """分析表单的action属性是否可疑（是否提交到外部域名）。

        钓鱼网站可能将表单数据提交到攻击者控制的服务器。

        Args:
            form_action: 表单action属性的值
            page_domain: 当前页面域名

        Returns:
            dict: {
                "form_action_suspicious": bool,  # action是否可疑
                "form_action_url": str,          # 解析后的action URL
                "is_external": bool,             # 是否指向外部域名
            }
        """
        if not form_action:
            return {
                "form_action_suspicious": False,
                "form_action_url": "",
                "is_external": False,
            }

        # 解析action URL
        try:
            action_parsed = urlparse(form_action)
        except Exception:
            return {
                "form_action_suspicious": False,
                "form_action_url": form_action,
                "is_external": False,
            }

        action_domain = action_parsed.netloc or action_parsed.hostname or ""

        # 如果没有域名（相对路径），则属于同一站点
        if not action_domain:
            return {
                "form_action_suspicious": False,
                "form_action_url": form_action,
                "is_external": False,
            }

        # 判断是否为外部域名
        # 标准化域名比较（去除www前缀等）
        page_domain_clean = re.sub(r'^www\.', '', page_domain.lower())
        action_domain_clean = re.sub(r'^www\.', '', action_domain.lower())

        is_external = page_domain_clean != action_domain_clean

        # 只有指向外部域名时才标记为可疑
        form_action_suspicious = is_external

        if is_external:
            logger.warning(
                f"检测到表单action指向外部域名: {form_action}, "
                f"页面域名: {page_domain}"
            )

        return {
            "form_action_suspicious": form_action_suspicious,
            "form_action_url": form_action,
            "is_external": is_external,
        }

    # ==================== 综合分析 ====================

    def analyze(self, html_content: str, page_url: str) -> dict:
        """综合分析页面中的表单：检测敏感字段和分析action。

        Args:
            html_content: 页面HTML内容
            page_url: 页面URL

        Returns:
            dict: 融合了字段检测和action检测的完整分析结果
        """
        # 从URL中提取域名
        page_domain = ""
        try:
            parsed = urlparse(page_url)
            page_domain = parsed.netloc or parsed.hostname or ""
        except Exception:
            pass

        # 分析表单字段
        field_result = self.analyze_form_fields(html_content)

        # 分析所有表单的action
        action_results = []
        overall_suspicious = field_result["has_sensitive_fields"]

        if html_content:
            try:
                soup = BeautifulSoup(html_content, "html.parser")
                forms = soup.find_all("form")
                for form in forms:
                    action = form.get("action", "")
                    if action:
                        action_result = self.analyze_form_action(action, page_domain)
                        action_results.append(action_result)
                        if action_result["form_action_suspicious"]:
                            overall_suspicious = True
            except Exception as e:
                logger.error(f"表单action分析失败: {e}")

        return {
            "has_sensitive_fields": field_result["has_sensitive_fields"],
            "sensitive_field_types": field_result["sensitive_field_types"],
            "form_count": field_result["form_count"],
            "input_count": field_result["input_count"],
            "sensitive_input_details": field_result["sensitive_input_details"],
            "form_actions": action_results,
            "overall_form_suspicious": overall_suspicious,
        }