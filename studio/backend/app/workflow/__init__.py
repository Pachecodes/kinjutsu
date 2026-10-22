"""Pure, side-effect free workflow construction for MiniMax H3.

Import the submodules directly (`from app.workflow.builder import ...`). This
package intentionally re-exports nothing: `app.schemas` depends on
`app.workflow.constants`, and `app.workflow.builder` depends on `app.schemas`,
so eager re-exports here would be a circular import.
"""
