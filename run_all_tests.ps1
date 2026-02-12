Set-Location "c:\Users\seanp\Workspace\ecom-agents"
$env:PYTHONUTF8 = "1"
$env:PYTHONPATH = "."

& .\.venv\Scripts\python.exe -m pytest `
    tests/test_holly_autonomy.py `
    tests/test_holly_introspection.py `
    tests/test_holly_eyes.py `
    tests/test_github_writer_mcp.py `
    tests/test_code_change_workflow.py `
    tests/test_deploy_workflow.py `
    tests/test_holly_ops_tools.py `
    tests/test_aws_ecs_mcp.py `
    tests/test_api_costs_mcp.py `
    tests/test_shopify_analytics_mcp.py `
    tests/test_revenue_seed.py `
    tests/test_holly_agent.py `
    tests/test_crew.py `
    -v --tb=short 2>&1
