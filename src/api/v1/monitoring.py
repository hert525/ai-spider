"""
监控API - 提供指标查询和代理健康状态。

从 wukong 移植并适配 FastAPI 路由。
"""
from __future__ import annotations

from fastapi import APIRouter, Depends

from src.core.auth import get_current_user

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/metrics")
async def get_metrics(user: dict = Depends(get_current_user)):
    """获取当前采集的指标数据"""
    from src.engine.metrics import get_collector
    collector = get_collector()
    result = {}
    for name, metric in collector.get_all_metrics().items():
        result[name] = {
            "type": metric.metric_type,
            "doc": metric.doc,
            "values": {str(k): v for k, v in metric._values.items()},
        }
    return {"metrics": result}


@router.get("/metrics/summary")
async def get_metrics_summary(user: dict = Depends(get_current_user)):
    """获取指标摘要（Dashboard用）"""
    from src.engine.metrics import get_collector
    collector = get_collector()
    all_metrics = collector.get_all_metrics()

    summary = {
        "total_requests": 0,
        "fetch_success": 0,
        "fetch_failures": 0,
        "success_rate": 0.0,
    }

    # 汇总请求计数
    req_metric = all_metrics.get("spider_http_requests_total")
    if req_metric:
        summary["total_requests"] = int(sum(req_metric._values.values()))

    success_metric = all_metrics.get("spider_fetch_success_total")
    if success_metric:
        summary["fetch_success"] = int(sum(success_metric._values.values()))

    fail_metric = all_metrics.get("spider_fetch_failures_total")
    if fail_metric:
        summary["fetch_failures"] = int(sum(fail_metric._values.values()))

    total = summary["fetch_success"] + summary["fetch_failures"]
    if total > 0:
        summary["success_rate"] = round(summary["fetch_success"] / total * 100, 1)

    return summary


@router.get("/proxy/stats")
async def get_proxy_stats(user: dict = Depends(get_current_user)):
    """获取代理池统计信息"""
    # 这里返回增强代理管理器的统计（如果有全局实例的话）
    return {"message": "使用任务级代理管理器，统计随任务返回", "stats": {}}


@router.get("/rate-limiter/status")
async def get_rate_limiter_status(user: dict = Depends(get_current_user)):
    """获取限速器状态"""
    from src.engine.nodes.fetch import get_rate_limiter
    limiter = get_rate_limiter()
    global_count = await limiter._global.count()
    return {
        "enabled": limiter.enabled,
        "global_qps_current": global_count,
        "global_qps_limit": limiter._global.max_requests,
    }


@router.post("/metrics/push")
async def trigger_metrics_push(user: dict = Depends(get_current_user)):
    """手动触发指标推送到 Pushgateway"""
    from src.engine.metrics import get_pusher
    pusher = get_pusher()
    success = await pusher.push()
    return {"pushed": success}
