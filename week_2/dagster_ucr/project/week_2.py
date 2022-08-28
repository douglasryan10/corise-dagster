from typing import List

from dagster import In, Nothing, Out, ResourceDefinition, graph, op
from dagster_ucr.project.types import Aggregation, Stock
from dagster_ucr.resources import mock_s3_resource, redis_resource, s3_resource


@op(
    config_schema={"s3_key": str},
    required_resource_keys={"s3"},
    out={"stocks": Out(dagster_type=List[Stock])},
    tags={"kind": "s3"},
    description="Get a list of stocks from an S3 file",
)
def get_s3_data(context):
    stocks = []
    for stock in context.resources.s3.get_data(context.op_config["s3_key"]):
        stocks.append(Stock.from_list(stock))
    return stocks


@op(
    ins={"stocks": In(dagster_type=List[Stock])},
    out=Out(dagster_type=Aggregation),
    description="Get an aggregation of the highest stock",
)
def process_data(stocks: List[Stock]) -> Aggregation:
    """
    Returns the aggregated Stock with the greatest high value
    from a list of Stocks
    """
    max_stock = max(stocks, key=lambda stock: stock.high)
    return Aggregation(date=max_stock.date, high=max_stock.high)


@op(
    required_resource_keys={"redis"},
    ins={"max_stock": In(dagster_type=Aggregation)},
    out=Out(dagster_type=Nothing),
)
def put_redis_data(context, max_stock: Aggregation):
    context.resources.redis.put_data(str(max_stock.date), str(max_stock.high))


@graph
def week_2_pipeline():
    put_redis_data(process_data(get_s3_data()))


local = {
    "ops": {"get_s3_data": {"config": {"s3_key": "prefix/stock.csv"}}},
}

docker = {
    "resources": {
        "s3": {
            "config": {
                "bucket": "dagster",
                "access_key": "test",
                "secret_key": "test",
                "endpoint_url": "http://host.docker.internal:4566",
            }
        },
        "redis": {
            "config": {
                "host": "redis",
                "port": 6379,
            }
        },
    },
    "ops": {"get_s3_data": {"config": {"s3_key": "prefix/stock.csv"}}},
}

local_week_2_pipeline = week_2_pipeline.to_job(
    name="local_week_2_pipeline",
    config=local,
    resource_defs={"s3": mock_s3_resource, "redis": ResourceDefinition.mock_resource()},
)

docker_week_2_pipeline = week_2_pipeline.to_job(
    name="docker_week_2_pipeline",
    config=docker,
    resource_defs={"s3": s3_resource, "redis": redis_resource},
)
