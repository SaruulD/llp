# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'LLP Payroll',
    'category': 'Hidden',
    'summary': 'Payroll',
    'website': '',
    'description': """
    Payroll
    """,
    'depends': ['hr', 'base', 'mail'],
    'data': [
        'security/security.xml',    
        'security/ir.model.access.csv',
        'views/llp_payroll_rule_views.xml',
        'views/llp_payroll_structure_views.xml',
        'views/llp_payroll_employee_vacation_views.xml',
        'views/llp_payroll_employee_debt_views.xml',
        'views/llp_payroll_unit_views.xml',
        'views/llp_payroll_views.xml',
        'views/menu_views.xml',
        'wizard/llp_payroll_payment_request_views.xml',
        'wizard/llp_payroll_account_move_views.xml',
    ],
    'installable': True,
    'application': True,
    'version': '18.1.0',
    'license': 'LGPL-3',
    'assets' : {
        'web.assets_backend': [
            'llp_payroll/static/src/js/llp_payroll_sheet.js',
            'llp_payroll/static/src/css/payroll_table.css',
            'llp_payroll/static/src/xml/llp_payroll_sheet.xml',
        ],
        # 'web.assets_qweb': [
        #     'llp_payroll/static/src/xml/llp_payroll_sheet.xml',
        # ],
    }, 
}
