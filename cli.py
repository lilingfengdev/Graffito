#!/usr/bin/env python3
"""
OQQWall CLI 管理工具
"""
import asyncio
import sys
import json
from pathlib import Path
from typing import Optional

import click
from loguru import logger
from tabulate import tabulate

from config import get_settings
from core.database import get_db, close_db
from core.models import Submission, BlackList, StoredPost


@click.group()
def cli():
    """OQQWall 命令行管理工具"""
    pass


@cli.command()
def config():
    """查看配置信息"""
    settings = get_settings()
    
    click.echo("=== 系统配置 ===")
    click.echo(f"调试模式: {settings.system.debug}")
    click.echo(f"日志级别: {settings.system.log_level}")
    click.echo(f"数据目录: {settings.system.data_dir}")
    
    click.echo("\n=== 服务器配置 ===")
    click.echo(f"监听地址: {settings.server.host}:{settings.server.port}")
    
    click.echo("\n=== 账号组配置 ===")
    for name, group in settings.account_groups.items():
        click.echo(f"\n组名: {name}")
        click.echo(f"  管理群: {group.manage_group_id}")
        click.echo(f"  主账号: {group.main_account.qq_id} (端口: {group.main_account.http_port})")
        if group.minor_accounts:
            click.echo(f"  副账号:")
            for minor in group.minor_accounts:
                click.echo(f"    - {minor.qq_id} (端口: {minor.http_port})")


@cli.command()
@click.option('--status', type=click.Choice(['all', 'pending', 'approved', 'rejected']), default='pending')
@click.option('--limit', type=int, default=10)
def list_submissions(status, limit):
    """查看投稿列表"""
    async def _list():
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            from core.enums import SubmissionStatus
            
            stmt = select(Submission)
            if status != 'all':
                status_map = {
                    'pending': SubmissionStatus.PENDING,
                    'approved': SubmissionStatus.APPROVED,
                    'rejected': SubmissionStatus.REJECTED
                }
                stmt = stmt.where(Submission.status == status_map[status].value)
                
            stmt = stmt.order_by(Submission.created_at.desc()).limit(limit)
            
            result = await session.execute(stmt)
            submissions = result.scalars().all()
            
            if not submissions:
                click.echo("没有找到投稿")
                return
                
            data = []
            for sub in submissions:
                data.append([
                    sub.id,
                    sub.sender_id,
                    sub.status,
                    sub.is_anonymous,
                    sub.created_at.strftime('%Y-%m-%d %H:%M:%S') if sub.created_at else ''
                ])
                
            headers = ['ID', '发送者', '状态', '匿名', '创建时间']
            click.echo(tabulate(data, headers=headers, tablefmt='grid'))
            
        await close_db()
        
    asyncio.run(_list())


@cli.command()
@click.argument('submission_id', type=int)
@click.argument('action', type=click.Choice(['approve', 'reject', 'delete']))
@click.option('--comment', help='审核评论')
def audit(submission_id, action, comment):
    """审核投稿"""
    async def _audit():
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select, update
            from core.enums import SubmissionStatus, AuditAction
            from core.models import AuditLog
            
            # 获取投稿
            stmt = select(Submission).where(Submission.id == submission_id)
            result = await session.execute(stmt)
            submission = result.scalar_one_or_none()
            
            if not submission:
                click.echo(f"投稿 {submission_id} 不存在")
                return
                
            # 更新状态
            status_map = {
                'approve': SubmissionStatus.APPROVED,
                'reject': SubmissionStatus.REJECTED,
                'delete': SubmissionStatus.DELETED
            }
            
            submission.status = status_map[action].value
            if comment:
                submission.comment = comment
                
            # 添加审核日志
            audit_log = AuditLog(
                submission_id=submission_id,
                operator_id='cli_admin',
                action=action,
                comment=comment
            )
            session.add(audit_log)
            
            await session.commit()
            click.echo(f"投稿 {submission_id} 已{action}")
            
        await close_db()
        
    asyncio.run(_audit())


@cli.command()
@click.argument('user_id')
@click.argument('group_name')
@click.option('--reason', help='拉黑原因')
def blacklist_add(user_id, group_name, reason):
    """添加黑名单"""
    async def _add():
        db = await get_db()
        async with db.get_session() as session:
            blacklist = BlackList(
                user_id=user_id,
                group_name=group_name,
                reason=reason or '未提供原因',
                operator_id='cli_admin'
            )
            session.add(blacklist)
            await session.commit()
            
            click.echo(f"用户 {user_id} 已添加到组 {group_name} 的黑名单")
            
        await close_db()
        
    asyncio.run(_add())


@cli.command()
@click.argument('user_id')
@click.argument('group_name')
def blacklist_remove(user_id, group_name):
    """移除黑名单"""
    async def _remove():
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select, delete
            
            stmt = delete(BlackList).where(
                (BlackList.user_id == user_id) &
                (BlackList.group_name == group_name)
            )
            result = await session.execute(stmt)
            
            if result.rowcount > 0:
                await session.commit()
                click.echo(f"用户 {user_id} 已从组 {group_name} 的黑名单移除")
            else:
                click.echo(f"用户 {user_id} 不在组 {group_name} 的黑名单中")
                
        await close_db()
        
    asyncio.run(_remove())


@cli.command()
def blacklist_list():
    """查看黑名单列表"""
    async def _list():
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            
            stmt = select(BlackList).order_by(BlackList.created_at.desc())
            result = await session.execute(stmt)
            blacklists = result.scalars().all()
            
            if not blacklists:
                click.echo("黑名单为空")
                return
                
            data = []
            for bl in blacklists:
                data.append([
                    bl.user_id,
                    bl.group_name,
                    bl.reason,
                    bl.created_at.strftime('%Y-%m-%d %H:%M:%S') if bl.created_at else ''
                ])
                
            headers = ['用户ID', '组名', '原因', '添加时间']
            click.echo(tabulate(data, headers=headers, tablefmt='grid'))
            
        await close_db()
        
    asyncio.run(_list())


@cli.command()
def db_init():
    """初始化数据库"""
    async def _init():
        click.echo("正在初始化数据库...")
        db = await get_db()
        
        if await db.health_check():
            click.echo("数据库初始化成功")
        else:
            click.echo("数据库初始化失败")
            
        await close_db()
        
    asyncio.run(_init())


@cli.command()
@click.option('--group', help='账号组名')
def flush_posts(group):
    """立即发送暂存的投稿"""
    async def _flush():
        if not group:
            click.echo("请指定账号组名")
            return
            
        db = await get_db()
        async with db.get_session() as session:
            from sqlalchemy import select
            
            stmt = select(StoredPost).where(StoredPost.group_name == group)
            result = await session.execute(stmt)
            posts = result.scalars().all()
            
            if not posts:
                click.echo(f"组 {group} 没有暂存的投稿")
                return
                
            click.echo(f"找到 {len(posts)} 个暂存的投稿")
            
            # TODO: 调用发送器发送
            click.echo("发送功能待实现...")
            
        await close_db()
        
    asyncio.run(_flush())


@cli.command()
def test_db():
    """测试数据库连接"""
    async def _test():
        try:
            db = await get_db()
            if await db.health_check():
                click.echo("✅ 数据库连接正常")
            else:
                click.echo("❌ 数据库连接失败")
        except Exception as e:
            click.echo(f"❌ 数据库连接异常: {e}")
        finally:
            await close_db()
            
    asyncio.run(_test())


if __name__ == '__main__':
    # 在cli.py的依赖中添加
    # pip install click tabulate
    cli()
