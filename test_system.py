#!/usr/bin/env python3
"""
Edge-VoMID 系统测试脚本
用于验证分布式声纹认证中间件的功能
"""
import os
import sys
import time
import requests
import json
from pathlib import Path

# 添加项目根目录到Python路径
sys.path.insert(0, str(Path(__file__).parent))

from client import VoMIDClient, VoMIDException


def test_basic_functionality():
    """测试基本功能"""
    print("=" * 60)
    print("Edge-VoMID 系统功能测试")
    print("=" * 60)
    
    # 检查测试音频文件
    test_files = ["test/test0.wav", "test/test1.wav", "test/test2.wav"]
    for test_file in test_files:
        if not os.path.exists(test_file):
            print(f"❌ 测试文件不存在: {test_file}")
            return False
    
    print("✅ 测试音频文件检查通过")
    
    try:
        # 创建客户端
        client = VoMIDClient("http://localhost:8080")
        
        # 测试健康检查
        print("\n🔍 测试健康检查...")
        health = client.health_check()
        print(f"✅ 健康检查通过: {health.get('status', 'unknown')}")
        
        # 测试声纹注册
        print("\n📝 测试声纹注册...")
        user_id_1 = client.register_voiceprint(
            name="测试用户1",
            audio_file="test/test0.wav",
            metadata={"department": "测试", "role": "测试员"}
        )
        print(f"✅ 用户1注册成功: {user_id_1}")
        
        user_id_2 = client.register_voiceprint(
            name="测试用户2", 
            audio_file="test/test1.wav",
            metadata={"department": "测试", "role": "测试员"}
        )
        print(f"✅ 用户2注册成功: {user_id_2}")
        
        # 测试声纹验证
        print("\n🔐 测试声纹验证...")
        
        # 验证用户1的声纹
        result_1 = client.verify_voiceprint(
            audio_file="test/test0.wav",
            threshold=0.6
        )
        print(f"✅ 用户1验证结果: {result_1.verified}, 置信度: {result_1.confidence:.4f}")
        
        # 验证用户2的声纹
        result_2 = client.verify_voiceprint(
            audio_file="test/test1.wav", 
            threshold=0.6
        )
        print(f"✅ 用户2验证结果: {result_2.verified}, 置信度: {result_2.confidence:.4f}")
        
        # 测试跨用户验证（应该失败）
        result_cross = client.verify_voiceprint(
            audio_file="test/test2.wav",
            threshold=0.6
        )
        print(f"✅ 跨用户验证结果: {result_cross.verified}, 置信度: {result_cross.confidence:.4f}")
        
        # 测试获取声纹信息
        print("\n📊 测试获取声纹信息...")
        info_1 = client.get_voiceprint(user_id_1)
        print(f"✅ 用户1信息: {info_1.name}, 状态: {info_1.status}")
        
        # 测试列出声纹
        print("\n📋 测试列出声纹记录...")
        voiceprints = client.list_voiceprints(limit=10)
        print(f"✅ 声纹记录总数: {voiceprints['total']}")
        
        # 测试统计信息
        print("\n📈 测试获取统计信息...")
        stats = client.get_statistics()
        print(f"✅ 统计信息获取成功")
        print(f"   声纹引擎统计: {stats.get('voiceprint_engine', {})}")
        print(f"   存储统计: {stats.get('distributed_storage', {})}")
        
        # 测试集群状态
        print("\n🌐 测试获取集群状态...")
        cluster_status = client.get_cluster_status()
        print(f"✅ 集群状态获取成功")
        print(f"   总节点数: {cluster_status.get('total_nodes', 0)}")
        print(f"   健康节点数: {cluster_status.get('healthy_nodes', 0)}")
        
        print("\n" + "=" * 60)
        print("🎉 所有测试通过！系统功能正常")
        print("=" * 60)
        
        return True
        
    except VoMIDException as e:
        print(f"❌ VoMID错误: {e}")
        return False
    except Exception as e:
        print(f"❌ 未知错误: {e}")
        return False


def test_performance():
    """测试性能"""
    print("\n" + "=" * 60)
    print("性能测试")
    print("=" * 60)
    
    try:
        client = VoMIDClient("http://localhost:8080")
        
        # 测试注册性能
        print("\n⏱️  测试注册性能...")
        start_time = time.time()
        
        for i in range(3):
            user_id = client.register_voiceprint(
                name=f"性能测试用户{i}",
                audio_file="test/test0.wav"
            )
            print(f"   注册 {i+1}: {user_id}")
        
        register_time = time.time() - start_time
        print(f"✅ 注册性能: 3次注册耗时 {register_time:.2f}秒")
        
        # 测试验证性能
        print("\n⏱️  测试验证性能...")
        start_time = time.time()
        
        for i in range(5):
            result = client.verify_voiceprint(
                audio_file="test/test0.wav",
                threshold=0.6
            )
            print(f"   验证 {i+1}: {result.verified}, 耗时 {result.processing_time:.3f}秒")
        
        verify_time = time.time() - start_time
        print(f"✅ 验证性能: 5次验证总耗时 {verify_time:.2f}秒")
        
        return True
        
    except Exception as e:
        print(f"❌ 性能测试失败: {e}")
        return False


def test_api_endpoints():
    """测试API端点"""
    print("\n" + "=" * 60)
    print("API端点测试")
    print("=" * 60)
    
    base_url = "http://localhost:8080"
    
    endpoints = [
        ("/health", "健康检查"),
        ("/api/v1/stats", "统计信息"),
        ("/api/v1/voiceprints", "声纹列表"),
        ("/api/v1/cluster/status", "集群状态"),
        ("/api/v1/storage/stats", "存储统计")
    ]
    
    success_count = 0
    
    for endpoint, description in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}", timeout=10)
            if response.status_code == 200:
                print(f"✅ {description}: {endpoint}")
                success_count += 1
            else:
                print(f"❌ {description}: {endpoint} (状态码: {response.status_code})")
        except Exception as e:
            print(f"❌ {description}: {endpoint} (错误: {e})")
    
    print(f"\n✅ API端点测试完成: {success_count}/{len(endpoints)} 成功")
    return success_count == len(endpoints)


def main():
    """主函数"""
    print("Edge-VoMID 分布式声纹认证中间件 - 系统测试")
    print("作者: AI Assistant")
    print("版本: 1.0.0")
    
    # 检查服务是否运行
    try:
        response = requests.get("http://localhost:8080/health", timeout=5)
        if response.status_code != 200:
            print("❌ 服务未运行或无法访问，请先启动服务")
            print("   启动命令: python main.py")
            return False
    except:
        print("❌ 无法连接到服务，请先启动服务")
        print("   启动命令: python main.py")
        return False
    
    # 运行测试
    tests = [
        ("基本功能测试", test_basic_functionality),
        ("性能测试", test_performance), 
        ("API端点测试", test_api_endpoints)
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n🚀 开始 {test_name}...")
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ {test_name} 执行失败: {e}")
            results.append((test_name, False))
    
    # 输出测试结果
    print("\n" + "=" * 60)
    print("测试结果汇总")
    print("=" * 60)
    
    passed = 0
    for test_name, result in results:
        status = "✅ 通过" if result else "❌ 失败"
        print(f"{test_name}: {status}")
        if result:
            passed += 1
    
    print(f"\n总计: {passed}/{len(results)} 测试通过")
    
    if passed == len(results):
        print("\n🎉 所有测试通过！系统运行正常")
        return True
    else:
        print(f"\n⚠️  有 {len(results) - passed} 个测试失败，请检查系统配置")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
