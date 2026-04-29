"""ui/dialogs — Dialog package for Time Tracker."""
from .goal_dialogs import AddGoalDialog, EditGoalDialog
from .task_dialogs import NewTaskDialog, RenameTaskDialog, MoveTaskDialog
from .category_dialogs import NewCategoryDialog, RenameCategoryDialog, RecolorCategoryDialog
from .session_dialogs import EditSessionDialog, AddSessionDialog
from .preset_dialog import AddCustomPresetDialog

__all__ = [
    "AddGoalDialog", "EditGoalDialog",
    "NewTaskDialog", "RenameTaskDialog", "MoveTaskDialog",
    "NewCategoryDialog", "RenameCategoryDialog", "RecolorCategoryDialog",
    "EditSessionDialog", "AddSessionDialog",
    "AddCustomPresetDialog",
]
