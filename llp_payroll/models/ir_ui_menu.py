# -*- coding: utf-8 -*-
from odoo import models


class IrUiMenu(models.Model):
    _inherit = 'ir.ui.menu'

    def _load_menus_blacklist(self):
        # hr_contract нь "Гэрээнүүд" цэсийг зөвхөн гэрээний ажилтан менежерт үлдээдэг тул
        # цалингийн нягтланд блэклистээс хасч харуулна.
        res = super()._load_menus_blacklist()
        if self.env.user.has_group('llp_payroll.group_payroll_accountant'):
            menu = self.env.ref('hr_contract.menu_hr_employee_contracts', raise_if_not_found=False)
            if menu:
                res = [menu_id for menu_id in res if menu_id != menu.id]
        return res
