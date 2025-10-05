"""Chisel AI 审核处理器"""
import json
import logging
from typing import Dict, Any, Optional
from openai import AsyncOpenAI

from config import get_settings
from core.models import Report, Submission, PlatformComment
from core.enums import ModerationLevel, ReportStatus, ModerationAction
from services.report_service import ReportService

logger = logging.getLogger(__name__)


class ModeratorProcessor:
    """Chisel AI 审核处理器"""
    
    def __init__(self):
        """初始化处理器"""
        settings = get_settings()
        self.api_key = settings.llm.api_key
        self.base_url = settings.llm.base_url or 'https://api.openai.com/v1'
        self.client = AsyncOpenAI(api_key=self.api_key, base_url=self.base_url)
        self.model = settings.llm.text_model or 'gpt-4o-mini'
        self.timeout = settings.llm.timeout or 30
        self.max_retry = settings.llm.max_retry or 3
        
        # Chisel 配置
        self.config = settings.chisel
        self.enabled = self.config.enable
        self.auto_delete = self.config.auto_delete
        self.auto_pass = self.config.auto_pass
        self.fetch_comments = self.config.fetch_comments
        self.comment_fetch_limit = self.config.comment_fetch_limit
    
    async def process_report(self, report: Report, submission: Submission) -> Dict[str, Any]:
        """处理举报
        
        Args:
            report: 举报记录
            submission: 投稿记录
            
        Returns:
            Dict: 处理结果
        """
        if not self.enabled:
            logger.info("Chisel 功能未开启")
            return {'success': False, 'message': 'Chisel 功能未开启'}
        
        try:
            # 1. 获取投稿的 AI 总结
            submission_summary = self._extract_submission_summary(submission)
            
            # 2. 获取平台评论
            comments = await ReportService.get_platform_comments(submission.id)
            comments_text = self._format_comments(comments)
            
            # 3. 构建 AI 审核提示
            prompt = self._build_moderation_prompt(
                submission_summary=submission_summary,
                comments=comments_text,
                report_reason=report.reason or "无"
            )
            
            # 4. 调用 AI 进行审核
            ai_result = await self._call_ai_moderation(prompt)
            
            if not ai_result:
                display_id = submission.publish_id or submission.id
                logger.error(f"AI 审核失败: 投稿 {display_id}（举报 ID: {report.id}）")
                return {'success': False, 'message': 'AI 审核失败'}
            
            # 5. 更新举报的 AI 审核结果
            await ReportService.update_ai_result(
                report_id=report.id,
                level=ai_result['level'],
                reason=ai_result['reason']
            )
            
            # 6. 根据配置和 AI 结果进行自动处理
            auto_handled = await self._auto_handle_report(report, submission, ai_result)
            
            return {
                'success': True,
                'ai_result': ai_result,
                'auto_handled': auto_handled
            }
            
        except Exception as e:
            logger.error(f"处理举报失败: {e}", exc_info=True)
            return {'success': False, 'message': str(e)}
    
    def _extract_submission_summary(self, submission: Submission) -> str:
        """提取投稿总结
        
        Args:
            submission: 投稿记录
            
        Returns:
            str: 投稿总结
        """
        try:
            # 使用 publish_id（用户可见的发布编号）或内部 id
            display_id = submission.publish_id or submission.id
            
            # 从数据库中的 llm_result 提取 AI 生成的 summary
            if submission.llm_result and isinstance(submission.llm_result, dict):
                summary = submission.llm_result.get('summary', '').strip()
                if summary:
                    logger.debug(f"提取到投稿 {display_id} 的 summary: {summary[:50]}...")
                    return summary
            
            logger.warning(f"投稿 {display_id} 缺少 llm_result 或 summary 字段")
            return "无内容摘要"
            
        except Exception as e:
            display_id = submission.publish_id or submission.id
            logger.error(f"提取投稿 {display_id} 总结失败: {e}", exc_info=True)
            return "无内容摘要"
    
    def _format_comments(self, comments: list) -> str:
        """格式化评论
        
        Args:
            comments: 评论列表
            
        Returns:
            str: 格式化后的评论文本
        """
        if not comments:
            return "暂无评论"
        
        formatted = []
        for comment in comments:
            platform = comment.platform
            author = comment.author_name or comment.author_id or "匿名"
            content = comment.content or ""
            created_at = comment.created_at.strftime("%Y-%m-%d %H:%M:%S") if comment.created_at else "未知时间"
            
            formatted.append(f"[{platform}] {author} ({created_at}): {content}")
        
        return "\n".join(formatted)
    
    def _build_moderation_prompt(
        self,
        submission_summary: str,
        comments: str,
        report_reason: str
    ) -> str:
        """构建审核提示
        
        Args:
            submission_summary: 投稿总结
            comments: 评论内容
            report_reason: 举报理由
            
        Returns:
            str: 审核提示
        """
        prompt = f"""你是一位经验丰富的内容审核员，拥有丰富的内容审核和管理经验。请按照以下指示回答问题和完成任务，以下是辅助信息

以下内容是用户投稿内容的总结：

{submission_summary}

以下内容是一组按时间顺序排列的校园墙投稿的评论记录：

{comments}

以下是用户举报的理由:

{report_reason}

请根据以下标准进行审核:

- 评论/投稿出现**大量**攻击性言论、辱骂内容、敏感政治信息
- 出现违反平台政策的内容比如色情/血腥内容
- 评论人数(传播范围指数)
- 用户举报理由

### 你需要给出的判断

- `level` 包含下面三个等级

`danger`

该投稿已经严重违反上面的规则,出现大量的不合法评论,危险程度极高,传播范围极广,已经产生严重后果

`warning`

该投稿的内容/评论已经出现违反上面的规则的地方,出现少量的不合法评论,传播范围少,在未来可能出现严重后果

`safe`

该投稿的内容/评论没有违反上面的规则,没有不合法评论,不会产生严重后果

- `reason` 你做出上面分级的原因

### 输出格式

**严格按照 JSON 格式输出**

{{
    "level": "danger|warning|safe",
    "reason": "你的分析理由"
}}
"""
        return prompt
    
    async def _call_ai_moderation(self, prompt: str) -> Optional[Dict[str, Any]]:
        """调用 AI 进行审核（使用流式响应）
        
        Args:
            prompt: 审核提示
            
        Returns:
            Dict: AI 审核结果 {'level': str, 'reason': str}
        """
        for attempt in range(self.max_retry):
            try:
                # 使用流式响应避免超时
                stream = await self.client.chat.completions.create(
                    model=self.model,
                    messages=[
                        {"role": "system", "content": "你是一个专业的内容审核 AI，严格按照 JSON 格式返回审核结果。"},
                        {"role": "user", "content": prompt}
                    ],
                    timeout=1000,
                    stream=True
                )
                
                # 收集流式响应
                content = ""
                async for chunk in stream:
                    if chunk.choices[0].delta.content is not None:
                        content += chunk.choices[0].delta.content
                
                content = content.strip()
                logger.debug(f"AI 审核原始响应: {content}")
                
                # 尝试解析 JSON
                # 处理可能的 markdown 代码块
                if content.startswith('```'):
                    content = content.split('```')[1]
                    if content.startswith('json'):
                        content = content[4:]
                    content = content.strip()
                
                result = json.loads(content)
                
                # 验证结果
                if 'level' in result and 'reason' in result:
                    level = result['level'].lower()
                    if level in ['danger', 'warning', 'safe']:
                        logger.info(f"AI 审核完成: level={level}")
                        return {
                            'level': level,
                            'reason': result['reason']
                        }
                
                logger.warning(f"AI 返回格式不正确: {content}")
                
            except json.JSONDecodeError as e:
                logger.error(f"AI 返回的 JSON 解析失败 (尝试 {attempt + 1}/{self.max_retry}): {e}")
                logger.error(f"原始内容: {content if 'content' in locals() else 'N/A'}")
            except Exception as e:
                logger.error(f"调用 AI 失败 (尝试 {attempt + 1}/{self.max_retry}): {e}", exc_info=True)
        
        return None
    
    async def _auto_handle_report(
        self,
        report: Report,
        submission: Submission,
        ai_result: Dict[str, Any]
    ) -> Optional[str]:
        """根据 AI 结果自动处理举报
        
        Args:
            report: 举报记录
            submission: 投稿记录
            ai_result: AI 审核结果
            
        Returns:
            Optional[str]: 处理动作，None 表示需要人工审核
        """
        level = ai_result['level']
        reason = ai_result['reason']
        
        # 使用 publish_id（用户可见的发布编号）或内部 id
        display_id = submission.publish_id or submission.id
        
        # danger: 自动删除（如果配置了）
        if level == ModerationLevel.DANGER.value and self.auto_delete:
            await ReportService.process_report(
                report_id=report.id,
                action=ModerationAction.AUTO_DELETE.value,
                reason=f"AI 自动删除: {reason}",
                processed_by="LLM"
            )
            logger.info(f"自动删除投稿 {display_id}（举报 ID: {report.id}）")
            return ModerationAction.AUTO_DELETE.value
        
        # safe: 自动通过（如果配置了）
        elif level == ModerationLevel.SAFE.value and self.auto_pass:
            await ReportService.process_report(
                report_id=report.id,
                action=ModerationAction.AUTO_PASS.value,
                reason=f"AI 自动通过: {reason}",
                processed_by="LLM"
            )
            logger.info(f"自动通过投稿 {display_id} 的举报（举报 ID: {report.id}）")
            return ModerationAction.AUTO_PASS.value
        
        # warning 或其他情况: 进入人工审核
        else:
            await ReportService.set_manual_review(report.id)
            logger.info(f"投稿 {display_id} 的举报（举报 ID: {report.id}）进入人工审核")
            return None


# 全局单例
_moderator_processor: Optional[ModeratorProcessor] = None


def get_moderator_processor() -> ModeratorProcessor:
    """获取审核处理器单例"""
    global _moderator_processor
    if _moderator_processor is None:
        _moderator_processor = ModeratorProcessor()
    return _moderator_processor

