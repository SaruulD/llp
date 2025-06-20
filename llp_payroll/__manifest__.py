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
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'version': '18.1.0',
    'license': 'LGPL-3',
}
