"""SVG 渲染器完整测试套件

测试所有支持的消息类型和渲染功能
"""
import asyncio
import sys
from pathlib import Path
from datetime import datetime

# 添加项目路径
sys.path.insert(0, str(Path(__file__).parent))

from processors.svg_renderer import SVGRenderer

# SVG 转 PNG 功能
def svg_to_png(svg_path: Path, png_path: Path, dpi: int = 96) -> bool:
    """使用 cairosvg 将 SVG 转换为 PNG（更可靠）"""
    try:
        import cairosvg
        
        # 使用 cairosvg 直接转换
        cairosvg.svg2png(
            url=str(svg_path),
            write_to=str(png_path),
            dpi=dpi
        )
        
        return True
    except ImportError:
        print(f"  ⚠️  缺少 cairosvg 库")
        print(f"  提示: pip install cairosvg")
        return False
    except Exception as e:
        print(f"  ✗ 转换失败: {e}")
        return False


async def test_svg_renderer():
    """测试 SVG 渲染器的完整功能"""
    
    print("=" * 60)
    print("SVG 渲染器完整测试")
    print("=" * 60)
    print()
    
    # 初始化渲染器
    print("📦 初始化 SVG 渲染器...")
    renderer = SVGRenderer()
    await renderer.initialize()
    print("✓ 渲染器初始化成功")
    print()
    
    # 准备完整的测试数据
    test_data = {
        'sender_id': '123456789',
        'nickname': '测试用户',
        'is_anonymous': False,
        'watermark_text': '测试水印',
        'wall_mark': 'XWall 测试墙',
        'messages': [
            # 1. 简单文本消息
            {
                'type': 'text',
                'data': {'text': '这是一条简单的文本消息'}
            },
            # 2. 多行文本消息
            {
                'type': 'text',
                'data': {'text': '这是第一行文本\n这是第二行文本\n这是第三行，包含一些较长的内容用于测试自动换行功能'}
            },
            # 3. 带链接的文本
            {
                'type': 'text',
                'data': {'text': '欢迎访问我的网站：https://example.com 了解更多信息'}
            },
            # 4. 超长文本（测试自动换行）
            {
                'type': 'text',
                'data': {'text': '这是一条非常非常非常非常非常非常非常非常非常长的消息，用于测试SVG渲染器的自动换行功能是否正常工作。'}
            },
            # 5. 文件消息
            {
                'type': 'file',
                'data': {
                    'file': 'project_report.pdf',
                    'file_size': 2548576  # 2.5 MB
                }
            },
            # 6. 图片消息（占位符，实际环境需要真实图片路径）
            {
                'type': 'image',
                'data': {'url': 'https://via.placeholder.com/400x300'}
            },
            # 7. 视频消息
            {
                'type': 'video',
                'data': {'url': 'video.mp4'}
            },
            # 8. 回复消息
            {
                'type': 'reply',
                'data': {
                    'id': '12345',
                    'text': '这是被引用的原始消息内容',
                    'name': '原作者'
                }
            },
            # 9. 回复后的内容
            {
                'type': 'text',
                'data': {'text': '我同意你的观点！'}
            },
            # 10. 小表情消息（使用实际存在的表情 ID）
            {
                'type': 'face',
                'data': {
                    'id': '5',
                    'raw': {'faceText': '[微笑]', 'faceType': 1}
                }
            },
            # 10.5 大表情/贴纸（使用实际存在的表情 ID）
            {
                'type': 'face',
                'data': {
                    'id': '100',
                    'raw': {'faceText': '[大笑]', 'faceType': 2}
                }
            },
            # 11. 戳一戳
            {
                'type': 'poke',
                'data': {}
            },
            # 12. JSON卡片消息
            {
                'type': 'json',
                'data': {
                    'data': {
                        'view': 'news',
                        'prompt': '分享了一条链接',
                        'meta': {
                            'news': {
                                'title': '重要通知：系统升级维护',
                                'desc': '系统将于明天凌晨2点进行升级维护',
                                'tag': '通知',
                                'jumpUrl': 'https://example.com/news/123'
                            }
                        }
                    }
                }
            },
            # 13. 小程序卡片
            {
                'type': 'json',
                'data': {
                    'data': {
                        'view': 'miniapp',
                        'meta': {
                            'miniapp': {
                                'title': '投票小程序',
                                'source': '投票助手',
                                'jumpUrl': 'https://example.com/vote'
                            }
                        }
                    }
                }
            },
            # 14. 联系人卡片
            {
                'type': 'json',
                'data': {
                    'data': {
                        'view': 'contact',
                        'meta': {
                            'contact': {
                                'nickname': '客服小助手',
                                'contact': 'QQ: 10000',
                                'avatar': 'https://via.placeholder.com/48',
                                'tag': '官方客服'
                            }
                        }
                    }
                }
            },
            # 15. 合并转发
            {
                'type': 'forward',
                'data': {
                    'messages': [
                        [
                            {'type': 'text', 'data': {'text': '转发消息1'}},
                        ],
                        [
                            {'type': 'text', 'data': {'text': '转发消息2'}},
                        ]
                    ]
                }
            },
            # 16. 结束语
            {
                'type': 'text',
                'data': {'text': '以上是全部测试消息内容，感谢使用！'}
            },
        ]
    }
    
    # 渲染 SVG
    print("🎨 开始渲染 SVG...")
    result = await renderer.process(test_data)
    
    svg_content = result.get('rendered_svg', '')
    extracted_links = result.get('extracted_links', [])
    
    if not svg_content:
        print("✗ 渲染失败：未生成 SVG 内容")
        return False
    
    print(f"✓ SVG 渲染成功，长度: {len(svg_content)} 字符")
    
    # 保存到文件
    output_file = Path('test_svg_output.svg')
    output_file.write_text(svg_content, encoding='utf-8')
    print(f"✓ SVG 已保存到: {output_file.absolute()}")
    print()
    
    # 统计信息
    print("📊 渲染统计:")
    print(f"  - 消息总数: {len(test_data['messages'])}")
    print(f"  - 提取链接: {len(extracted_links)} 个")
    if extracted_links:
        for i, link in enumerate(extracted_links, 1):
            print(f"    {i}. {link}")
    else:
        print("    (无链接)")
    print()
    
    # 文件信息
    file_size = output_file.stat().st_size
    print("📄 输出文件信息:")
    print(f"  - 文件路径: {output_file.absolute()}")
    print(f"  - 文件大小: {file_size:,} 字节 ({file_size/1024:.2f} KB)")
    print(f"  - SVG 行数: {svg_content.count(chr(10)) + 1}")
    print()
    
    # 转换为 PNG
    print("🖼️  转换为 PNG...")
    
    # 创建输出目录
    output_dir = Path('test_output')
    output_dir.mkdir(exist_ok=True)
    
    png_file = output_dir / 'test_svg_output.png'
    
    if svg_to_png(output_file, png_file, dpi=96):
        png_size = png_file.stat().st_size
        print(f"✓ PNG 已保存到: {png_file.absolute()}")
        print(f"  文件大小: {png_size:,} 字节 ({png_size/1024:.2f} KB)")
    else:
        print(f"✗ PNG 转换失败")
    
    print()
    
    # 提示后续操作
    print("💡 后续操作:")
    print(f"  - 在浏览器中打开 SVG: file:///{output_file.absolute()}")
    print(f"  - 查看 PNG 输出: {png_file.absolute()}")
    print()
    
    return True


async def test_anonymous_mode():
    """测试匿名模式"""
    print("=" * 60)
    print("测试匿名模式")
    print("=" * 60)
    print()
    
    renderer = SVGRenderer()
    await renderer.initialize()
    
    test_data = {
        'sender_id': '10000',
        'nickname': '匿名',
        'is_anonymous': True,
        'watermark_text': '匿名投稿',
        'wall_mark': 'XWall',
        'messages': [
            {'type': 'text', 'data': {'text': '这是一条匿名消息'}},
            {'type': 'text', 'data': {'text': '我想匿名分享一些想法'}},
        ]
    }
    
    result = await renderer.process(test_data)
    svg_content = result.get('rendered_svg', '')
    
    output_file = Path('test_svg_anonymous.svg')
    output_file.write_text(svg_content, encoding='utf-8')
    
    print(f"✓ 匿名模式 SVG 已保存到: {output_file.absolute()}")
    
    # 转换为 PNG
    output_dir = Path('test_output')
    output_dir.mkdir(exist_ok=True)
    png_file = output_dir / 'test_svg_anonymous.png'
    
    if svg_to_png(output_file, png_file, dpi=96):
        print(f"✓ PNG 已保存到: {png_file.absolute()}")
    
    print()
    
    return True


async def test_long_message():
    """测试超长消息"""
    print("=" * 60)
    print("测试超长消息")
    print("=" * 60)
    print()
    
    renderer = SVGRenderer()
    await renderer.initialize()
    
    # 生成长文本
    long_text = "这是一段很长的测试文本。" * 50
    
    test_data = {
        'sender_id': '123456',
        'nickname': '长文测试',
        'watermark_text': '测试',
        'wall_mark': 'XWall',
        'messages': [
            {'type': 'text', 'data': {'text': long_text}},
            {'type': 'text', 'data': {'text': '以上是一条超长消息的测试'}},
        ]
    }
    
    result = await renderer.process(test_data)
    svg_content = result.get('rendered_svg', '')
    
    output_file = Path('test_svg_long.svg')
    output_file.write_text(svg_content, encoding='utf-8')
    
    print(f"✓ 长消息 SVG 已保存到: {output_file.absolute()}")
    print(f"  - 文本长度: {len(long_text)} 字符")
    
    # 转换为 PNG
    output_dir = Path('test_output')
    output_dir.mkdir(exist_ok=True)
    png_file = output_dir / 'test_svg_long.png'
    
    if svg_to_png(output_file, png_file, dpi=96):
        print(f"✓ PNG 已保存到: {png_file.absolute()}")
    
    print()
    
    return True


async def main():
    """主测试函数"""
    print()
    print("╔" + "=" * 58 + "╗")
    print("║" + " " * 15 + "SVG 渲染器测试套件" + " " * 23 + "║")
    print("╚" + "=" * 58 + "╝")
    print()
    
    results = []
    
    # 测试1: 完整功能测试
    try:
        result = await test_svg_renderer()
        results.append(("完整功能测试", result))
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        results.append(("完整功能测试", False))
    
    # 测试2: 匿名模式
    try:
        result = await test_anonymous_mode()
        results.append(("匿名模式测试", result))
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        results.append(("匿名模式测试", False))
    
    # 测试3: 超长消息
    try:
        result = await test_long_message()
        results.append(("超长消息测试", result))
    except Exception as e:
        print(f"✗ 测试失败: {e}")
        results.append(("超长消息测试", False))
    
    # 总结
    print()
    print("=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    print()
    print(f"总计: {passed}/{total} 通过")
    
    if passed == total:
        print()
        print("🎉 所有测试通过！")
        print()
        print("生成的 SVG 文件:")
        print("  1. test_svg_output.svg (完整功能测试)")
        print("  2. test_svg_anonymous.svg (匿名模式)")
        print("  3. test_svg_long.svg (超长消息)")
        print()
        print("生成的 PNG 文件（在 test_output/ 目录）:")
        print("  1. test_svg_output.png")
        print("  2. test_svg_anonymous.png")
        print("  3. test_svg_long.png")
        print()
        print("📂 PNG 输出目录: test_output/")
    else:
        print()
        print("⚠ 部分测试失败，请检查错误信息")
    
    print()
    print("=" * 60)


if __name__ == '__main__':
    asyncio.run(main())
