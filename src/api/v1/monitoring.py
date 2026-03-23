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
        "successful_requests": 0,
        "failed_requests": 0,
        "total_extracted": 0,
        "total_deduped": 0,
        "active_tasks": 0,
        "success_rate": 0.0,
    }

    # 汇总请求计数
    req_metric = all_metrics.get("spider_http_requests_total")
    if req_metric:
        summary["total_requests"] = int(sum(req_metric._values.values()))

    success_metric = all_metrics.get("spider_fetch_success_total")
    if success_metric:
        summary["successful_requests"] = int(sum(success_metric._values.values()))

    fail_metric = all_metrics.get("spider_fetch_failures_total")
    if fail_metric:
        summary["failed_requests"] = int(sum(fail_metric._values.values()))

    extract_metric = all_metrics.get("spider_extracted_items_total")
    if extract_metric:
        summary["total_extracted"] = int(sum(extract_metric._values.values()))

    dedup_metric = all_metrics.get("spider_deduped_items_total")
    if dedup_metric:
        summary["total_deduped"] = int(sum(dedup_metric._values.values()))

    task_metric = all_metrics.get("spider_active_tasks")
    if task_metric:
        summary["active_tasks"] = int(sum(task_metric._values.values()))

    total = summary["successful_requests"] + summary["failed_requests"]
    if total > 0:
        summary["success_rate"] = round(summary["successful_requests"] / total * 100, 1)

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

    # 域名维度限速状态
    dimensions = {}
    if hasattr(limiter, '_domain_limiter') and limiter._domain_limiter:
        dl = limiter._domain_limiter
        for domain, counter in dl._counters.items():
            cnt = await counter.count()
            dimensions[domain] = {
                "limit": counter.max_requests,
                "current": cnt,
                "waiting": 0,
            }

    return {
        "enabled": limiter.enabled,
        "global": {
            "default_qps": limiter._global.max_requests,
            "current_concurrency": global_count,
            "pressure_level": "正常",
        },
        "dimensions": dimensions,
    }


@router.post("/metrics/push")
async def trigger_metrics_push(user: dict = Depends(get_current_user)):
    """手动触发指标推送到 Pushgateway"""
    from src.engine.metrics import get_pusher
    pusher = get_pusher()
    success = await pusher.push()
    return {"pushed": success}


# ── Alerting ──

@router.get("/alerts/history")
async def get_alert_history(limit: int = 50, user: dict = Depends(get_current_user)):
    """Get recent alert history."""
    from src.core.alerting import alert_manager
    return alert_manager.get_history(limit)


@router.get("/alerts/rules")
async def get_alert_rules(user: dict = Depends(get_current_user)):
    """Get alert rules."""
    from src.core.alerting import alert_manager
    return alert_manager.get_rules()
