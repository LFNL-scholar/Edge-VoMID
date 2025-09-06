import numpy as np
import torch
from modelscope.pipelines import pipeline
from modelscope.utils.constant import Tasks
import logging
from config.logger import setup_logging
# 禁用modelscope的日志输出
logging.getLogger('modelscope').setLevel(logging.CRITICAL)

# 初始化日志
logger = setup_logging()
logger = logger.bind(tag="app")

# 初始化
sv_pipeline = pipeline(
    task=Tasks.speaker_verification, model="iic/speech_campplus_sv_zh-cn_3dspeaker_16k"
)

voiceprints = {}


def _to_numpy(x):
    return x.cpu().numpy() if torch.is_tensor(x) else np.asarray(x)


def register_voiceprint(name, audio_path):
    """登记声纹特征"""
    result = sv_pipeline([audio_path], output_emb=True)
    emb = _to_numpy(result["embs"][0])  # 1 条音频只取第 0 条
    voiceprints[name] = emb
    logger.info(f"已登记声纹: {name}")


def identify_speaker(audio_path, threshold=0.6):
    """识别声纹所属（带阈值判断）"""
    test_result = sv_pipeline([audio_path], output_emb=True)
    test_emb = _to_numpy(test_result["embs"][0])

    similarities = {}
    for name, emb in voiceprints.items():
        cos_sim = np.dot(test_emb, emb) / (
            np.linalg.norm(test_emb) * np.linalg.norm(emb)
        )
        similarities[name] = cos_sim

    match_name = max(similarities, key=similarities.get)
    match_score = similarities[match_name]
    
    # 新增阈值判断
    if match_score < threshold:
        return None, match_score, similarities  # 返回None表示未匹配到可信说话人
    else:
        return match_name, match_score, similarities


if __name__ == "__main__":
    register_voiceprint("tts0", "test/test0.wav")
    register_voiceprint("tts1", "test/test1.wav")

    test_file = "test/test2.wav"
    threshold = 0.7  # 设置自定义阈值
    match_name, match_score, all_scores = identify_speaker(test_file, threshold)

    logger.info(f"识别结果: {test_file} 属于 {match_name if match_name else '未知说话人'}")
    if match_name is None:
        logger.warning("未匹配到可信说话人")
    else:
        logger.info(f"匹配说话人: {match_name}")
    logger.info(f"匹配分数: {match_score:.4f} (阈值: {threshold})")
    logger.info("所有声纹对比分数:")
    for name, score in all_scores.items():
        logger.info(f"{name}: {score:.4f}")
