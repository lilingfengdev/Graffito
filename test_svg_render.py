#!/usr/bin/env python3
"""SVG 渲染引擎测试脚本

测试 SVG 渲染器的基本功能
"""
import asyncio
from pathlib import Path

# 测试数据
test_data = {
    'submission_id': 'test_001',
    'sender_id': '123456',
    'nickname': '测试用户',
    'is_anonymous': False,
    'watermark_text': '测试水印',
    'wall_mark': 'SVG 测试墙',
    'messages': [
        {
            'type': 'text',
            'data': {'text': '这是一条测试文本消息'}
        },
        {
            'type': 'text',
            'data': {'text': '这是第二条消息，包含换行\n和多行文本\n测试渲染效果'}
        },
        {
            'type': 'file',
            'data': {
                'file': 'test_document.pdf',
                'file_size': 1024000
            }
        },
        {
            'type': 'reply',
            'data': {
                'text': '这是一条引用消息',
                'name': '引用者'
            }
        }
    ]
}


async def test_svg_renderer():
    """测试 SVG 渲染器"""
    print("开始测试 SVG 渲染器...")
    
    try:
        from processors.svg_renderer import SVGRenderer
        
        # 创建渲染器
        renderer = SVGRenderer()
        await renderer.initialize()
        
        print("✓ SVG 渲染器初始化成功")
        
        # 渲染测试数据
        print("\n渲染测试消息...")
        result = await renderer.process(test_data.copy())
        
        if 'rendered_svg' in result:
            svg_content = result['rendered_svg']
            print(f"✓ SVG 渲染成功，长度: {len(svg_content)} 字符")
            
            # 保存 SVG 到文件
            output_file = Path('test_output.svg')
            output_file.write_text(svg_content, encoding='utf-8')
            print(f"✓ SVG 已保存到: {output_file}")
            
            # 显示提取的链接
            extracted_links = result.get('extracted_links', [])
            if extracted_links:
                print(f"\n提取的链接: {extracted_links}")
            else:
                print("\n没有提取到链接")
                
        else:
            print("✗ 未生成 SVG 内容")
            return False
        
        await renderer.shutdown()
        print("\n✓ 所有测试通过!")
        return True
        
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_svg_backend():
    """测试 SVG 后端（需要安装 cairosvg 或 svglib）"""
    print("\n" + "="*60)
    print("开始测试 SVG 后端...")
    
    try:
        from processors.render_backends import SVGRenderBackend
        
        # 创建后端
        backend = SVGRenderBackend(use_cairo=True)
        await backend.initialize()
        
        print(f"✓ SVG 后端初始化成功 (转换器: {backend.converter})")
        
        # 创建简单的测试 SVG
        test_svg = '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="300" viewBox="0 0 400 300">
    <rect width="400" height="300" fill="#f0f0f0" />
    <text x="200" y="150" font-family="Arial" font-size="24" text-anchor="middle" fill="#333">
        SVG 渲染测试
    </text>
</svg>'''
        
        print("\n转换 SVG 为 PNG...")
        images = await backend.render_html_to_images(
            html=test_svg,
            submission_id='svg_test',
            output_dir='./test_output'
        )
        
        if images:
            print(f"✓ PNG 生成成功:")
            for img in images:
                print(f"  - {img}")
        else:
            print("✗ PNG 生成失败")
            return False
        
        await backend.shutdown()
        print("\n✓ SVG 后端测试通过!")
        return True
        
    except ImportError as e:
        print(f"\n⚠ 跳过 SVG 后端测试: 未安装转换库")
        print(f"  提示: pip install cairosvg 或 pip install svglib reportlab")
        return None
    except Exception as e:
        print(f"\n✗ SVG 后端测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_full_pipeline():
    """测试完整渲染管道"""
    print("\n" + "="*60)
    print("开始测试完整渲染管道...")
    
    try:
        from processors.svg_renderer import SVGRenderer
        from processors.render_backends import SVGRenderBackend
        
        # 创建渲染器和后端
        renderer = SVGRenderer()
        backend = SVGRenderBackend(use_cairo=True)
        
        await renderer.initialize()
        await backend.initialize()
        
        print("✓ 渲染管道初始化成功")
        
        # 步骤 1: 渲染 SVG
        print("\n步骤 1: 渲染消息为 SVG...")
        result = await renderer.process(test_data.copy())
        svg_content = result.get('rendered_svg')
        
        if not svg_content:
            print("✗ SVG 渲染失败")
            return False
        
        print(f"✓ SVG 渲染完成，长度: {len(svg_content)}")
        
        # 步骤 2: 转换为 PNG
        print("\n步骤 2: 转换 SVG 为 PNG...")
        images = await backend.render_html_to_images(
            html=svg_content,
            submission_id='pipeline_test',
            output_dir='./test_output'
        )
        
        if images:
            print(f"✓ 完整管道测试通过! 生成 {len(images)} 张图片:")
            for img in images:
                print(f"  - {img}")
        else:
            print("✗ PNG 转换失败")
            return False
        
        await renderer.shutdown()
        await backend.shutdown()
        
        print("\n" + "="*60)
        print("✓ 所有测试完成!")
        print("\n生成的文件:")
        print("  - test_output.svg (SVG 源文件)")
        print("  - test_output/pipeline_test/page_*.png (渲染结果)")
        
        return True
        
    except ImportError:
        print("\n⚠ 跳过完整管道测试: 未安装转换库")
        return None
    except Exception as e:
        print(f"\n✗ 完整管道测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


async def main():
    """运行所有测试"""
    print("="*60)
    print("SVG 渲染引擎测试套件")
    print("="*60)
    
    results = []
    
    # 测试 1: SVG 渲染器
    result1 = await test_svg_renderer()
    results.append(("SVG 渲染器", result1))
    
    # 测试 2: SVG 后端
    result2 = await test_svg_backend()
    if result2 is not None:
        results.append(("SVG 后端", result2))
    
    # 测试 3: 完整管道
    if result2:  # 只有后端测试通过才运行完整测试
        result3 = await test_full_pipeline()
        if result3 is not None:
            results.append(("完整管道", result3))
    
    # 汇总结果
    print("\n" + "="*60)
    print("测试结果汇总:")
    print("="*60)
    
    for name, result in results:
        status = "✓ 通过" if result else "✗ 失败"
        print(f"{name}: {status}")
    
    all_passed = all(r for _, r in results)
    if all_passed:
        print("\n🎉 所有测试通过!")
        return 0
    else:
        print("\n❌ 部分测试失败")
        return 1


if __name__ == '__main__':
    exit_code = asyncio.run(main())
    exit(exit_code)

