from odoo import api, fields, models, _
from odoo.exceptions import UserError
from odoo.tools import exception_to_unicode
import logging
import time
from datetime import date,datetime
from operator import itemgetter
_logger = logging.getLogger(__name__)

class LLPPayrollAccountMove(models.TransientModel):
    _name = 'llp.payroll.account.move'
    _description = 'Payroll Account Move Wizard'

    department_id = fields.Many2one('hr.department', string="Department", readonly=True)
    journal_id = fields.Many2one('account.journal', string="Journal", readonly=True)
    line_ids = fields.One2many('llp.payroll.account.move.line','account_move_line_id',string="Lines")

    @api.model
    def default_get(self, fields):
        res = super(LLPPayrollAccountMove, self).default_get(fields)
        payroll_id = self.env['llp.payroll'].browse(self._context.get('active_ids', []))
        unit_id = self.env['llp.payroll.unit'].search([('department_ids','in',payroll_id.department_id.id)], limit=1)

        res.update({
            'department_id': payroll_id.department_id.id, 
            'journal_id': unit_id.journal_id.id
        })

        move_lines = {}
        rules = []
        moves = []
        debt_debit_account_id = False
        debt_credit_account_id = False

        for obj in unit_id.line_ids:
            line = obj.sudo()

            if line.rule_id.transaction_type == 'by_partner':
                debt_debit_account_id = line.debit_account_id.id if line.debit_account_id else False
                debt_credit_account_id = line.credit_account_id.id if line.credit_account_id else False

            elif line.rule_id.id not in move_lines:
                move_lines[line.rule_id.id] = {
                    'rule': line.rule_id.id,
                    'debit_sum':0.0,
                    'credit_sum':0.0,
                    'debit_account_id': line.debit_account_id.id,
                    'credit_account_id': line.credit_account_id.id,
                    'internal_type':False,
                    'note': line.transaction_value,
                    'partners':{},
                    'department_id': payroll_id.department_id.id,
                }
                    
                if line.rule_id not in rules:
                    rules.append(line.rule_id)
                
        dbamount =  0.0

        for obj in payroll_id.line_ids:
            line= obj.sudo()
            cramount = 0.0
            for rule in line.rule_value_ids:
                if rule.payroll_rule_id.id in move_lines:
                    move_lines[rule.payroll_rule_id.id]['debit_sum'] += round(rule.value,2)
                    move_lines[rule.payroll_rule_id.id]['credit_sum'] += round(rule.value,2)

                    if round(rule.value,2) != 0.0:	
                        group_partner = line.employee_id.work_contact_id.id							
                        if group_partner not in move_lines[rule.payroll_rule_id.id]['partners']:
                            move_lines[rule.payroll_rule_id.id]['partners'][group_partner]={
                                'amount':0.0,
                                'partner_id': False,
                                'name':'',
                            }
                        move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['amount'] += round(rule.value,2)
                        move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['partner_id'] = group_partner
                        move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['name']= u'[%s - [%s]'%(move_lines[rule.payroll_rule_id.id]['note'],line.employee_id.name)

                if rule.payroll_rule_id.transaction_type == 'by_partner':
                    cramount += round(rule.value,2)
                
            if round(cramount,2)!=0.0:
                dbamount += round(cramount,2)
                moves_append = {
                    'name': u'[Цалин харилцагчаар задлах - [%s]'%(line.employee_id.name),
                    'debit': 0.0 ,
                    'credit': round(cramount,2),
                    'account_id': debt_credit_account_id,
                    'amount_currency': 0.0,
                }
                moves.append((0,0,moves_append))
            
        if round(dbamount,2) != 0.0:
            moves_append = {
                'name': u'[Цалин харилцагчаар задлах - %s]'%(payroll_id.department_id.name),
                'debit': round(dbamount,2) ,
                'credit': 0.0,
                'account_id': debt_debit_account_id,
                'amount_currency': 0.0,
            }
            moves.append((0,0,moves_append))

        for move in sorted(move_lines.values(), key=itemgetter('rule')):			
            if move['debit_sum'] != 0.0 and move['credit_sum'] != 0.0:						
                moves += self.defaut_get_create_move(move)
                        
        if moves:
            res.update({'line_ids': moves})
                
        return res
    
    def defaut_get_create_move(self, move):
        moves=[]
        if move['internal_type']=='credit' or not move['internal_type']:
            moves_append = {
                'name': u'[Цалин] %s'%(move['note']),
                'debit': round(move['debit_sum'],2)>0  and round(move['debit_sum'],2),
                'credit': round(move['debit_sum'],2)<0 and -1*round(move['debit_sum'],2),										
                'account_id': move['debit_account_id'],
                'amount_currency': 0.0,
            }
                
            moves.append((0,0,moves_append))
        
        # Credit
        if move['internal_type']=='debit' or not move['internal_type']:
            moves_append = {
                'name': u'[Цалин] %s'%(move['note']),
                'debit': round(move['debit_sum'],2)<0  and -1*round(move['debit_sum'],2),
                'credit': round(move['credit_sum'],2)>0 and round(move['credit_sum'],2),
                'account_id': move['credit_account_id'],
                'amount_currency': 0.0,
            }
            moves.append((0,0, moves_append))
        if move['internal_type']:
            for part in sorted(move['partners'].values(), key=itemgetter('partner_id')):	
                amount = round(part['amount'],2)>0 and round(part['amount'],2) or -1*round(part['amount'],2)
                account = move['internal_type']=='debit' and move['debit_account_id'] or move['credit_account_id']
                moves_append = {
                    'name': part['name'],
                    'debit': move['internal_type']=='debit' and amount or 0.0 ,
                    'credit': move['internal_type']=='credit' and amount or 0.0,
                    'account_id': account,
                    'amount_currency': 0.0,
                }
                moves.append((0,0,moves_append))
        return moves
    
    def clear_previous_moves_and_history(self, payroll_id):
        if not payroll_id or not payroll_id.payment_history_ids:
            return
        for his in payroll_id.payment_history_ids:
            if his.move_id:
                his.move_id.button_draft()
                his.unlink()
                self.env.cr.commit()

    def action_confirm(self):
        self.ensure_one()
        payroll_id = self.env['llp.payroll'].browse(self._context.get('active_ids', []))
        unit_id = self.env['llp.payroll.unit'].search([('department_ids','in',payroll_id.department_id.id)], limit=1)
        if not unit_id.line_ids:
            raise UserError(_('Журналын бичилтын тохиргоо хийгдээгүй байна!!!'))

        self.clear_previous_moves_and_history(payroll_id)

        mmoves= []
        rules = []
        move_lines = {}
        debt_debit_account_id = False
        debt_credit_account_id = False

        for obj in unit_id.line_ids:
            line = obj.sudo()
            
            if line.rule_id.transaction_type == 'by_partner':
                debt_debit_account_id = line.debit_account_id.id if line.debit_account_id else False
                debt_credit_account_id = line.credit_account_id.id if line.credit_account_id else False

            elif line.rule_id.id not in move_lines:
                move_lines[line.rule_id.id] = {
                    'rule': line.rule_id.id,
                    'debit_sum':0.0,
                    'credit_sum':0.0,
                    'debit_account_id': line.debit_account_id.id if line.debit_account_id else False,
                    'credit_account_id': line.credit_account_id.id if line.credit_account_id else False,
                    'internal_type':False,
                    'note': line.transaction_value,
                    # 'department_id':payroll_id.department_id.id,
                    'partners':{},
                }
        
                if line.rule_id not in rules:
                    rules.append(line.rule_id)
                
        moves = []
        dbamount =  0.0

        for obj in payroll_id.line_ids:
            line= obj.sudo()
            cramount = 0.0
            for rule in line.rule_value_ids:
                if rule.payroll_rule_id.id in move_lines:
                    if round(rule.value,2)!=0.0:	
                        move_lines[rule.payroll_rule_id.id]['debit_sum'] += round(rule.value,2)
                        move_lines[rule.payroll_rule_id.id]['credit_sum'] += round(rule.value,2)
                        group_partner = line.employee_id.work_contact_id.id							
                        if group_partner not in move_lines[rule.payroll_rule_id.id]['partners']:
                            move_lines[rule.payroll_rule_id.id]['partners'][group_partner]={
                                'amount':0.0,
                                'partner_id': False,
                                'name':'',
                            }
                        move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['amount'] +=round(rule.value,2)
                        move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['partner_id'] = group_partner
                        move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['name']= u'[%s - [%s]'%(move_lines[rule.payroll_rule_id.id]['note'],line.employee_id.name)

                if rule.payroll_rule_id.transaction_type == 'by_partner':
                    cramount += round(rule.value,2)
                    
            if round(cramount,2) != 0.0:
                dbamount += round(cramount,2)
                moves_append = {
                    'account_id': debt_credit_account_id,
                    'partner_id': line.employee_id.work_contact_id.id,
                    'name': u'[Цалин харилцагчаар задлах - [%s]'%(line.employee_id.name),
                    'debit': 0.0 ,
                    'credit': round(cramount,2),
                    # 'date_maturity': payroll_id.end_date,
                    # 'amount_currency': 0.0,
                    # 'currency_rate': 0.0,
                    # 'currency_id': False,
                    # 'quantity': 1,  
                    # 'department_id':payroll_id.department_id.id,
                }
                moves.append((0,0,moves_append))
                
        if round(dbamount,2)!=0.0:
            moves_append = {
                'account_id': debt_debit_account_id,
                'partner_id': False,
                'name': u'[Цалин харилцагчаар задлах - %s]'%(payroll_id.department_id.name),
                'debit': round(dbamount,2),
                'credit': 0.0,
                # 'amount_currency': 0.0,
                # 'currency_rate': 0.0,
                # 'currency_id': False,
                # 'quantity': 1,  
                # 'department_id':payroll_id.department_id.id,
            }
            moves.append((0,0,moves_append))
        if moves:
            move_vals = {
                'ref': u'%s [Цалин]'%payroll_id.start_date,
                'line_ids': moves,
                'journal_id': unit_id.journal_id.id,
                'date': payroll_id.end_date,
                # 'department_id':payroll_id.department_id.id,
            }
        
            try:
                move_id = self.env['account.move'].create(move_vals)
                mmoves.append(move_id.id)      
                self.env['payroll.payment.history'].create({'payroll_id':payroll_id.id,'move_id':move_id.id})
                self.env.cr.commit()
                move_id.action_post()
            except Exception as e:
                for mmove in mmoves:
                    move_id = self.env['account.move'].browse(mmove)
                    move_id.button_draft()
                self.env.cr.commit()
                raise UserError(_(u'Алдаа: %s '%(exception_to_unicode(e))))
        moves = []
        move_vals= {}

        for move in sorted(move_lines.values(), key=itemgetter('rule')):
            # Debit
            moves = []
            if move['debit_sum'] != 0 and move['credit_sum'] != 0:
                moves += self.create_move(move)
                if moves:
                    move_vals = {
                        'ref': u'%s [Цалин]'%payroll_id.start_date,
                        'line_ids': moves,
                        'journal_id': unit_id.journal_id.id,
                        'date': payroll_id.end_date,
                    }
                    try:
                        move_id = self.env['account.move'].create(move_vals)
                        mmoves.append(move_id.id)      
                        self.env['payroll.payment.history'].create({'payroll_id':payroll_id.id,'move_id':move_id.id})
                        self.env.cr.commit()
                        move_id.action_post()
                    except Exception as e:
                            for mmove in mmoves:
                                move_id = self.env['account.move'].browse(mmove)
                                move_id.button_draft()
                            self.env.cr.commit()
                            raise UserError(_(u'Алдаа: %s '%(exception_to_unicode(e))))
        
        
        self.env.cr.commit()
        
        return True
        # return {
        #     'domain': "[('id','in', [%s])]" % ','.join([str(p) for p in mmoves]),
        #     'name': _('Account move'),
        #     'view_type': 'form',
        #     'view_mode': 'tree,form',
        #     'res_model': 'account.move',
        #     'view_id': False,
        #     'type': 'ir.actions.act_window',
        #     # 'search_view_id': id['res_id']
        # }

    def create_move(self, move):
        moves=[]
        if move['internal_type'] == 'credit' or not move['internal_type']:
            moves_append = {
                'account_id': move['debit_account_id'],
                'partner_id': False,
                'name': u'[Цалин] %s'%(move['note']),
                'debit': round(move['debit_sum'],2)>0  and round(move['debit_sum'],2),
                'credit': round(move['debit_sum'],2)<0 and -1*round(move['debit_sum'],2),										
                # 'amount_currency': 0.0,
                # 'currency_rate': 0.0,
                # 'currency_id': False,
                # 'quantity': 1,  
                # 'department_id': move['department_id'],
            }
                
            moves.append((0,0,moves_append))
        
        # Credit
        if move['internal_type']=='debit' or not move['internal_type']:
            moves_append = {
                'account_id': move['credit_account_id'],
                'partner_id': False,
                'name': u'[Цалин] %s'%(move['note']),
                'debit': round(move['debit_sum'],2)<0  and -1*round(move['debit_sum'],2),
                'credit': round(move['credit_sum'],2)>0 and round(move['credit_sum'],2),
                # 'amount_currency': 0.0,
                # 'currency_rate': 0.0,
                # 'currency_id': False,
                # 'quantity': 1,  
                # 'department_id': move['department_id'],
            }
            moves.append((0,0, moves_append))
        if move['internal_type']:
            for part in sorted(move['partners'].values(), key=itemgetter('partner_id')):	
                amount = round(part['amount'],2)>0 and round(part['amount'],2) or -1*round(part['amount'],2)
                account = move['internal_type']=='debit' and move['debit_account_id'] or move['credit_account_id']
                moves_append = {
                    'account_id': account,
                    'partner_id': part['partner_id'],
                    'name': part['name'],
                    'debit': move['internal_type']=='debit' and amount or 0.0 ,
                    'credit': move['internal_type']=='credit' and amount or 0.0,
                    # 'amount_currency': 0.0,
                    # 'currency_rate': 0.0,
                    # 'currency_id': False,
                    # 'quantity': 1,   
                    # 'department_id': move['department_id'],
                }
                moves.append((0,0,moves_append))
        return moves

class LLPPayrollAccountMoveLine(models.TransientModel):
	_name ='llp.payroll.account.move.line'

	account_id = fields.Many2one('account.account',string="Account")
	credit = fields.Float(string="Credit")
	debit = fields.Float(string="Debit")
	amount_currency = fields.Float(string="Amount currency")
	name = fields.Char(String="Name")
	account_move_line_id = fields.Many2one('llp.payroll.account.move',string="Line")
