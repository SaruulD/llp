# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.
from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


class DynamicWorkflowConfirmWizard(models.TransientModel):
    _name = 'dynamic.workflow.confirm.wizard'
    _description = 'Dynamic Workflow Confirm Wizard'

    comment = fields.Text('Comment')
    comment_required = fields.Boolean('Comment required',default=False)
    approve_code = fields.Integer(default=1)    #approve: 1, return: 2 , cancel: 3

    def action_confirm(self):
        self.ensure_one()
        self._confirm()

    def _confirm(self):
        return 0