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

    department_id = fields.Many2one('hr.department', string="Department")
    journal_id = fields.Many2one('account.journal', string="Journal")
    line_ids = fields.One2many('llp.payroll.account.move.line','account_move_line_id',string="Lines")

    @api.model
    def default_get(self, fields):
        res = super(LLPPayrollAccountMove, self).default_get(fields)
        payroll_id = self.env['llp.payroll'].browse(self._context.get('active_ids', []))
        if payroll_id.unit_id.sector_id.nomin_code in['111','112','114','117','118','119','120','122','121','123','133','136'] :    
            res.update({'department_id':1253 })
        else:
            res.update({'department_id': payroll_id.unit_id.sector_id.id})
        payroll_ids = self.env['nomin.payroll'].browse(self._context.get('active_ids', []))
        move_lines = {}
        debt_debit_account_id = False
        debt_credit_account_id = False
        rules = []
        for payroll_id in payroll_ids:
            date_config = payroll_id.unit_id.sector_id.company_id.get_move_date_config(payroll_id.month_id.date_stop)

            for obj in payroll_id.unit_id.line_ids:
                line = obj.sudo()
                if line.rule_id.code =='n33001':
                    if date_config['is_diamond']:
                        debt_debit_account_id = line.debit_account_id.id
                        debt_credit_account_id = line.credit_account_id.id

                elif line.rule_id.id not in move_lines and line.rule_id.code != 'n35016':
                    move_lines[line.rule_id.id] = {
                        'rule': line.rule_id.id,
                        'debit_sum':0.0,
                        'credit_sum':0.0,
                        'debit_account_id': False,
                        'credit_account_id': False,
                        'internal_type':False,
                        'note': line.note,
                        'partners':{},
                        'department_id': payroll_id.unit_id.sector_id.id,
                    }
                    if date_config['is_diamond']:
                        move_lines[line.rule_id.id]['debit_account_id'] = line.debit_account_id.id
                        move_lines[line.rule_id.id]['credit_account_id'] = line.credit_account_id.id
                        if line.debit_account_id.internal_type=='receivable':
                            move_lines[line.rule_id.id]['internal_type'] = 'debit'
                        elif line.credit_account_id.internal_type=='receivable':
                            move_lines[line.rule_id.id]['internal_type'] = 'credit'
                        
                    if line.rule_id not in rules:
                        rules.append(line.rule_id)
                    
            moves = []
            dbamount =  0.0

            for obj in payroll_id.line_ids:
                line= obj.sudo()
                cramount = 0.0
                for rule in line.rule_value_ids:
                    if rule.payroll_rule_id.id in move_lines:
                        if rule.payroll_rule_id.code !='n33001' and rule.payroll_rule_id.code !='n33003' and rule.payroll_rule_id.code !='n32007':
                            move_lines[rule.payroll_rule_id.id]['debit_sum'] +=round(rule.value,2)
                            move_lines[rule.payroll_rule_id.id]['credit_sum'] +=round(rule.value,2)
                            if round(rule.value,2)!=0.0:	
                                group_partner = line.payroll_employee_id.employee_id.address_home_id.id							
                                if group_partner not in move_lines[rule.payroll_rule_id.id]['partners']:
                                    move_lines[rule.payroll_rule_id.id]['partners'][group_partner]={
                                        'amount':0.0,
                                        'partner_id': False,
                                        'name':'',
                                    }
                                move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['amount'] +=round(rule.value,2)
                                move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['partner_id'] = group_partner
                                move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['name']= u'[%s - [%s,%s]'%(move_lines[rule.payroll_rule_id.id]['note'],line.payroll_employee_id.employee_id.name,line.payroll_employee_id.employee_id.passport_id)

                    if rule.payroll_rule_id.transaction_type  =='debt':
                        cramount += round(rule.value,2)
                    
                if round(cramount,2)!=0.0:
                    dbamount += round(cramount,2)
                    moves_append = {
                        'name': u'[Цалин авлага - [%s,%s]'%(line.payroll_employee_id.employee_id.name,line.payroll_employee_id.employee_id.passport_id),
                        'debit': 0.0 ,
                        'credit': round(cramount,2),
                        'account_id': debt_credit_account_id,
                        'amount_currency': 0.0,
                    }
                    moves.append((0,0,moves_append))
                
            if round(dbamount,2) !=0.0:
                moves_append = {
                    'name': u'[Цалин авлага %s]'%(payroll_id.unit_id.sector_id.name),
                    'debit': round(dbamount,2) ,
                    'credit': 0.0,
                    'account_id': debt_debit_account_id,
                    'amount_currency': 0.0,
                }
                moves.append((0,0,moves_append))

            for move in sorted(move_lines.values(), key=itemgetter('rule')):			
                if move['debit_sum'] !=0.0 and move['credit_sum']!=0.0:						
                    moves+=self.defaut_get_create_move(move)
                        
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


    def action_confirm(self):
        payroll_id = self.env['nomin.payroll'].browse(self._context.get('active_ids', []))
        if not payroll_id.unit_id.line_ids:
            raise UserError(_('Журналын бичилтын тохиргоо хийгдээгүй байна!!!'))
        self.clear_previous_moves_and_history(payroll_id)

        mmoves= []
        rules = []
        move_lines = {}
        debt_debit_account_id = False
        debt_credit_account_id = False
        date_config = payroll_id.unit_id.sector_id.company_id.get_move_date_config(payroll_id.month_id.date_stop)
        is_diamond = date_config['is_diamond']

        for obj in payroll_id.unit_id.line_ids:
            line = obj.sudo()

            if is_diamond and not line.debit_account_id:
                raise UserError(_('Журналын бичилтийн данс /Diamond/ хоосон байна.!!!'))
            
            if line.rule_id.code =='n33001':
                debt_debit_account_id = line.debit_account_id.id if line.debit_account_id else False
                debt_credit_account_id = line.credit_account_id.id if line.credit_account_id else False
            elif line.rule_id.id not in move_lines and line.rule_id.code != 'n35016':
                move_lines[line.rule_id.id] = {
                    'rule': line.rule_id.id,
                    'debit_sum':0.0,
                    'credit_sum':0.0,
                    'debit_account_id': line.debit_account_id.id if line.debit_account_id else False,
                    'credit_account_id': line.credit_account_id.id if line.credit_account_id else False,
                    'internal_type':False,
                    'note': line.note,
                    'department_id':payroll_id.unit_id.sector_id.id,
                    'partners':{},
                }

                if is_diamond:
                    if line.debit_account_id and line.debit_account_id.internal_type == 'receivable':
                        move_lines[line.rule_id.id]['internal_type'] = 'debit'
                    elif line.credit_account_id and line.credit_account_id.internal_type == 'receivable':
                        move_lines[line.rule_id.id]['internal_type'] = 'credit'
        
                if line.rule_id not in rules:
                    rules.append(line.rule_id)
                
        moves = []
        dbamount =  0.0

        for obj in payroll_id.line_ids:
            line= obj.sudo()
            cramount = 0.0
            for rule in line.rule_value_ids:
                if rule.payroll_rule_id.id in move_lines:
                    if rule.payroll_rule_id.code not in ['n33001','n33003']:						
                        if round(rule.value,2)!=0.0:	
                            move_lines[rule.payroll_rule_id.id]['debit_sum'] +=round(rule.value,2)
                            move_lines[rule.payroll_rule_id.id]['credit_sum'] += round(rule.value,2)
                            group_partner = line.payroll_employee_id.employee_id.address_home_id.id							
                            if group_partner not in move_lines[rule.payroll_rule_id.id]['partners']:
                                move_lines[rule.payroll_rule_id.id]['partners'][group_partner]={
                                    'amount':0.0,
                                    'partner_id': False,
                                    'name':'',
                                }
                            move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['amount'] +=round(rule.value,2)
                            move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['partner_id'] = group_partner
                            move_lines[rule.payroll_rule_id.id]['partners'][group_partner]['name']= u'[%s - [%s,%s]'%(move_lines[rule.payroll_rule_id.id]['note'],line.payroll_employee_id.employee_id.name,line.payroll_employee_id.employee_id.passport_id)

                if rule.payroll_rule_id.transaction_type  =='debt':
                    cramount += round(rule.value,2)
                    
            if round(cramount,2)!=0.0:
                dbamount += round(cramount,2)
                moves_append = {
                    'date_maturity': payroll_id.month_id.date_stop,
                    'partner_id': line.payroll_employee_id.employee_id.address_home_id.id,
                    'name': u'[Цалин авлага - [%s,%s]'%(line.payroll_employee_id.employee_id.name,line.payroll_employee_id.employee_id.passport_id),
                    'debit': 0.0 ,
                    'credit': round(cramount,2),
                    'account_id': debt_credit_account_id,
                    'amount_currency': 0.0,
                    'currency_rate': 0.0,
                    'currency_id': False,
                    'quantity': 1,  
                    'department_id':payroll_id.unit_id.sector_id.id,
                }
                moves.append((0,0,moves_append))
                
        if round(dbamount,2)!=0.0:
            moves_append = {
                'date_maturity': payroll_id.month_id.date_stop,
                'partner_id': False,
                'name': u'[Цалин авлага %s]'%(payroll_id.unit_id.sector_id.name),
                'debit': round(dbamount,2),
                'credit': 0.0,
                'account_id': debt_debit_account_id,
                'amount_currency': 0.0,
                'currency_rate': 0.0,
                'currency_id': False,
                'quantity': 1,  
                'department_id':payroll_id.unit_id.sector_id.id,
            }
            moves.append((0,0,moves_append))
        if moves:
            move_vals = {
                'ref': u'%s [Цалин]'%payroll_id.month_id.name,
                'line_ids': moves,
                'journal_id': self.journal_id.id,
                'date': payroll_id.month_id.date_stop,
                'department_id':payroll_id.unit_id.sector_id.id,
            }
        
            try:
                move_id = self.env['account.move'].create(move_vals)
                mmoves.append(move_id.id)      
                self.env['payroll.payment.history'].create({'payroll_id':payroll_id.id,'move_id':move_id.id})
                self.env.cr.commit()
                move_id.self_post()
            except Exception as e:
                for mmove in mmoves:
                    move_id = self.env['account.move'].browse(mmove)
                    move_id.button_cancel()

                    _logger.info(u'nomin_account: Success deleted, Second action , Account move deleted.')
                self.env.cr.commit()
                raise UserError(_(u'Алдаа: %s '%(exception_to_unicode(e))))
        moves = []

        move_vals= {}
        for move in sorted(move_lines.values(), key=itemgetter('rule')):			
            # Debit
            moves = []
            if move['debit_sum']!=0 and move['credit_sum']!=0:
                moves+=self.create_move(payroll_id, move)
                if moves:
                    move_vals = {
                        'ref': u'%s [Цалин]'%payroll_id.month_id.name,
                        'line_ids': moves,
                        'journal_id': self.journal_id.id,
                        'date': payroll_id.month_id.date_stop,
                        'is_send_diamond':is_diamond,
                        'department_id':payroll_id.unit_id.sector_id.id,
                    }
                    try:
                        move_id = self.env['account.move'].create(move_vals)
                        mmoves.append(move_id.id)      
                        self.env['payroll.payment.history'].create({'payroll_id':payroll_id.id,'move_id':move_id.id})
                        self.env.cr.commit()
                        move_id.self_post()
                    except Exception as e:								
                            for mmove in mmoves:
                                move_id = self.env['account.move'].browse(mmove)
                                # if move_id.state != 'draft':
                                move_id.button_cancel()
                            self.env.cr.commit()
                            raise UserError(_(u'Алдаа: %s '%(exception_to_unicode(e))))
        
        
        self.env.cr.commit()
        

        return {
            'domain': "[('id','in', [%s])]" % ','.join([str(p) for p in mmoves]),
            'name': _('Account move'),
            'view_type': 'form',
            'view_mode': 'tree,form',
            'res_model': 'account.move',
            'view_id': False,
            'type': 'ir.actions.act_window',
            # 'search_view_id': id['res_id']
        }

class LLPPayrollAccountMoveLine(models.TransientModel):
	_name ='llp.payroll.account.move.line'

	account_id = fields.Many2one('account.account',string="Account")
	credit = fields.Float(string="Credit")
	debit = fields.Float(string="Debit")
	amount_currency = fields.Float(string="Amount currency")
	name = fields.Char(String="Name")
	account_move_line_id = fields.Many2one('llp.payroll.diamond.move',string="Line")
