# -*- coding: utf-8 -*-
# Part of Odoo. See LICENSE file for full copyright and licensing details.

{
    'name': 'LLP Dynamic Work Flow Base',
    'category': 'Hidden',
    'summary': 'Dynamic Work Flow',
    'website': '',
    'description': """
    Dynamic Work Flow base
    """,
    'depends': ['hr', 'base', 'mail'],
    'data': [
        'security/security.xml',    
        'security/ir.model.access.csv',
        'views/dynamic_workflow_views.xml',
        'views/dynamic_state_views.xml',
        'wizard/workflow_confirm_wizard.xml',
        'views/menu_views.xml',
    ],
    'installable': True,
    'application': True,
    'version': '18.1.0',
    'license': 'LGPL-3',
}
