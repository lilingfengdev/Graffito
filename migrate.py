#!/usr/bin/env python3
"""
OQQWall 数据迁移脚本
用于从旧版本(Shell版本)迁移到Python版本
"""
import json
import sqlite3
import asyncio
from pathlib import Path
from typing import Dict, Any, List
import click
from loguru import logger

from config import get_settings
from core.database import get_db
from core.models import Submission, BlackList
from core.enums import SubmissionStatus


class OldDataMigrator:
    """旧数据迁移器"""
    
    def __init__(self, old_path: str):
        self.old_path = Path(old_path)
        self.old_db_path = self.old_path / "cache" / "OQQWall.db"
        self.old_config_path = self.old_path / "oqqwall.config"
        self.old_account_path = self.old_path / "AcountGroupcfg.json"
        
    async def migrate(self):
        """执行迁移"""
        logger.info("开始数据迁移...")
        
        # 检查旧数据
        if not self.old_db_path.exists():
            logger.error(f"旧数据库不存在: {self.old_db_path}")
            return False
            
        # 迁移配置
        await self.migrate_config()
        
        # 迁移数据库
        await self.migrate_database()
        
        # 迁移缓存文件
        await self.migrate_cache()
        
        logger.info("数据迁移完成")
        return True
        
    async def migrate_config(self):
        """迁移配置文件"""
        logger.info("迁移配置文件...")
        
        # 读取旧配置
        old_config = {}
        if self.old_config_path.exists():
            with open(self.old_config_path, 'r') as f:
                for line in f:
                    if '=' in line:
                        key, value = line.strip().split('=', 1)
                        old_config[key.strip()] = value.strip().strip('"')
                        
        # 读取账号组配置
        old_accounts = {}
        if self.old_account_path.exists():
            with open(self.old_account_path, 'r', encoding='utf-8') as f:
                old_accounts = json.load(f)
                
        # 转换为新配置格式
        new_config = {
            'system': {
                'debug': False,
                'log_level': 'INFO',
                'data_dir': './data',
                'cache_dir': './data/cache'
            },
            'server': {
                'host': '0.0.0.0',
                'port': int(old_config.get('http-serv-port', 8082))
            },
            'database': {
                'type': 'sqlite',
                'url': 'sqlite+aiosqlite:///./data/oqqwall.db',
                'pool_size': 10
            },
            'llm': {
                'provider': 'dashscope',
                'api_key': old_config.get('apikey', ''),
                'text_model': old_config.get('text_model', 'qwen-plus-latest'),
                'vision_model': old_config.get('vision_model', 'qwen-vl-max-latest'),
                'timeout': 30,
                'max_retry': 3
            },
            'processing': {
                'wait_time': int(old_config.get('process_waittime', 120)),
                'max_concurrent': 10
            },
            'receivers': {
                'qq': {
                    'enabled': True,
                    'http_port': int(old_config.get('http-serv-port', 8082)),
                    'auto_accept_friend': True,
                    'friend_request_window': int(old_config.get('friend_request_window_sec', 300))
                }
            },
            'publishers': {
                'qzone': {
                    'enabled': True,
                    'max_attempts': int(old_config.get('max_attempts_qzone_autologin', 3)),
                    'batch_size': 30,
                    'max_images_per_post': 9,
                    'send_schedule': []
                }
            },
            'audit': {
                'auto_approve': False,
                'ai_safety_check': True,
                'sensitive_words': []
            },
            'account_groups': {}
        }
        
        # 转换账号组配置
        for group_name, group_data in old_accounts.items():
            new_group = {
                'name': group_name,
                'manage_group_id': group_data.get('mangroupid', ''),
                'main_account': {
                    'qq_id': group_data.get('mainqqid', ''),
                    'http_port': int(group_data.get('mainqq_http_port', 3000))
                },
                'minor_accounts': [],
                'max_post_stack': int(group_data.get('max_post_stack', 1)),
                'max_images_per_post': int(group_data.get('max_image_number_one_post', 30)),
                'send_schedule': group_data.get('send_schedule', []),
                'watermark_text': group_data.get('watermark_text', ''),
                'friend_add_message': group_data.get('friend_add_message', ''),
                'quick_replies': group_data.get('quick_replies', {})
            }
            
            # 转换副账号
            minorqqids = group_data.get('minorqqid', [])
            minorqq_ports = group_data.get('minorqq_http_port', [])
            for i, qqid in enumerate(minorqqids):
                if i < len(minorqq_ports):
                    new_group['minor_accounts'].append({
                        'qq_id': qqid,
                        'http_port': int(minorqq_ports[i])
                    })
                    
            new_config['account_groups'][group_name] = new_group
            
        # 保存新配置
        import yaml
        config_path = Path('config/config.yaml')
        config_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(new_config, f, allow_unicode=True, default_flow_style=False)
            
        logger.info(f"配置已保存到: {config_path}")
        
    async def migrate_database(self):
        """迁移数据库"""
        logger.info("迁移数据库...")
        
        # 连接旧数据库
        old_conn = sqlite3.connect(self.old_db_path)
        old_cursor = old_conn.cursor()
        
        # 获取新数据库
        db = await get_db()
        
        # 迁移sender表到submissions
        try:
            old_cursor.execute("SELECT * FROM sender")
            senders = old_cursor.fetchall()
            
            async with db.get_session() as session:
                for row in senders:
                    # 解析旧数据
                    senderid, receiver, acgroup, rawmsg, modtime, processtime = row
                    
                    # 创建新投稿
                    submission = Submission(
                        sender_id=senderid,
                        receiver_id=receiver,
                        group_name=acgroup,
                        raw_content=json.loads(rawmsg) if rawmsg else [],
                        status=SubmissionStatus.PENDING.value
                    )
                    session.add(submission)
                    
                await session.commit()
                logger.info(f"迁移了 {len(senders)} 个投稿")
                
        except Exception as e:
            logger.error(f"迁移投稿失败: {e}")
            
        # 迁移黑名单
        try:
            old_cursor.execute("SELECT * FROM blocklist")
            blocklists = old_cursor.fetchall()
            
            async with db.get_session() as session:
                for row in blocklists:
                    senderid, acgroup, receiver, reason = row
                    
                    blacklist = BlackList(
                        user_id=senderid,
                        group_name=acgroup,
                        reason=reason,
                        operator_id='migrated'
                    )
                    session.add(blacklist)
                    
                await session.commit()
                logger.info(f"迁移了 {len(blocklists)} 个黑名单记录")
                
        except Exception as e:
            logger.error(f"迁移黑名单失败: {e}")
            
        old_conn.close()
        
    async def migrate_cache(self):
        """迁移缓存文件"""
        logger.info("迁移缓存文件...")
        
        # 迁移cookies
        old_cookies_dir = self.old_path
        new_cookies_dir = Path('data/cookies')
        new_cookies_dir.mkdir(parents=True, exist_ok=True)
        
        for cookie_file in old_cookies_dir.glob('cookies-*.json'):
            qqid = cookie_file.stem.replace('cookies-', '')
            new_file = new_cookies_dir / f'qzone_{qqid}.json'
            
            with open(cookie_file, 'r') as f:
                cookies = json.load(f)
                
            with open(new_file, 'w') as f:
                json.dump(cookies, f)
                
            logger.info(f"迁移cookies: {cookie_file.name} -> {new_file.name}")
            
        # 迁移编号文件
        old_numb_dir = self.old_path / 'cache' / 'numb'
        if old_numb_dir.exists():
            for numb_file in old_numb_dir.glob('*_numfinal.txt'):
                group_name = numb_file.stem.replace('_numfinal', '')
                
                with open(numb_file, 'r') as f:
                    number = f.read().strip()
                    
                # 保存到新数据库或配置
                logger.info(f"组 {group_name} 的当前编号: {number}")


@click.command()
@click.argument('old_path', type=click.Path(exists=True))
def main(old_path):
    """迁移旧版本数据到新版本
    
    OLD_PATH: 旧版本OQQWall的根目录路径
    """
    click.echo("=== OQQWall 数据迁移工具 ===")
    click.echo(f"旧版本路径: {old_path}")
    
    if not click.confirm("确认开始迁移？"):
        click.echo("迁移已取消")
        return
        
    migrator = OldDataMigrator(old_path)
    
    async def run():
        success = await migrator.migrate()
        if success:
            click.echo("✅ 迁移成功")
        else:
            click.echo("❌ 迁移失败")
            
    asyncio.run(run())


if __name__ == '__main__':
    main()
