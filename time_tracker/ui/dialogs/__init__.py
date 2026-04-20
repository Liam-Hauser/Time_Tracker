"""ui/dialogs — Dialog package for Time Tracker."""
from .goal_dialogs import AddGoalDialog, EditGoalDialog
from .task_dialogs import NewTaskDialog, RenameTaskDialog, MoveTaskDialog
from .category_dialogs import NewCategoryDialog, RenameCategoryDialog
from .session_dialogs import EditSessionDialog, AddSessionDialog

__all__ = [
    "AddGoalDialog", "EditGoalDialog",
    "NewTaskDialog", "RenameTaskDialog", "MoveTaskDialog",
    "NewCategoryDialog", "RenameCategoryDialog",
    "EditSessionDialog", "AddSessionDialog",
]
