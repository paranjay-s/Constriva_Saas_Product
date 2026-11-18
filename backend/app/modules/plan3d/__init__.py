"""3D houses: the gateway to the private PlanTo3D service (services/planto3d).

PlanTo3D has no login and must never be reachable from outside. Everything a browser does
with it goes through this module at /api/v1/3d, which signs users in, checks that a job is
theirs, and forwards the request. See docs/08-3d.md.
"""
