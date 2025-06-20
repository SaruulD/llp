from odoo import fields, models, _


class DynamicState(models.Model):
    _name = 'dynamic.state'
    _description = 'Dynamic States'

    _order = 'sequence'

    name = fields.Char('Name')
    state = fields.Char('State')
    is_dynamic = fields.Boolean('Is Dynamic', default=True)
    sequence = fields.Integer('Sequence', default=0)