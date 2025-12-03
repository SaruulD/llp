# -*- coding: utf-8 -*-

from odoo import api, fields, models, _ # type: ignore
from odoo.exceptions import UserError # type: ignore
from dateutil.relativedelta import relativedelta # type: ignore
import logging
import re
_logger = logging.getLogger(__name__)
from operator import itemgetter
from odoo.tools.safe_eval import safe_eval # type: ignore

class LLPPayroll(models.Model):
    _name = 'llp.payroll'
    _inherit = ['mail.thread']
    _description = "LLP payroll"
    _order = "create_date desc"

    def _model_id_domain(self):
        model = self.env['ir.model']._get(self._name)
        return [('model_id', '=', model.id)]

    name = fields.Char(string='Code',tracking=True, readonly=True)
    start_date = fields.Date(string="Start Date", required=True, tracking=True)
    end_date = fields.Date(string="End Date", required=True, tracking=True)
    dynamic_workflow_id = fields.Many2one(
        'dynamic.workflow',
        string="Dynamic workflow",
        domain=_model_id_domain,
    )
	
    department_id = fields.Many2one('hr.department',string="Department",tracking=True)
	
    struct_id = fields.Many2one('llp.payroll.structure',string="Stucture", domain="[('state','=','done')]",tracking=True)
    line_ids = fields.One2many('llp.payroll.line','payroll_id',string="Lines")

    state = fields.Selection([
        ('draft','Draft'),
        ('sent','Sent'),
        ('pending','Pending'),
        ('verify','Verify'),
        ('confirmed','Confirmed'),
        ('done','Done'),
        ('closed','Closed')
    ],string='State',default='draft',tracking=True)
    
    @api.model
    def create(self, vals):
        seq_code = 'llp.payroll.seq'
        if not self.env['ir.sequence'].sudo().search([('code', '=', seq_code)], limit=1):
            self.env['ir.sequence'].sudo().create({
                'name': 'LLP Payroll Sequence',
                'code': seq_code,
                'prefix': 'PA/%(year)s/',
                'padding': 4,
                'number_next': 1,
                'number_increment': 1,
            })

        vals['name'] = self.env['ir.sequence'].next_by_code(seq_code) or '/'

        result = super(LLPPayroll, self).create(vals)
        return result
    
    def action_send(self):
        if not self.line_ids:
            raise UserError((u'Ажилтнуудын мэдээлэл алга байна.'))
        self.write({'state':'sent'})
        
    def action_approve(self):
        self.write({'state':'pending'})

    def action_verify(self):
        self.write({'state':'verify'})

    def action_return(self):
        self.write({'state':'draft'})

    def action_confirm(self):
        self.write({'state':'confirmed'})

    def action_payment_request(self):
        self.ensure_one()
        action = self.env.ref('llp_payroll.action_llp_payroll_payment_request').read()[0]
        # Pass defaults via context
        action['context'] = {
            # 'default_company_id': self.company_id.id if hasattr(self, 'company_id') else self.env.company.id,
            # 'default_currency_id': self.currency_id.id,
            # 'payroll_type': self.payroll_type,
            # 'payroll_month': self.payroll_month and self.payroll_month.strftime('%Y-%m-%d') or False,
            # 'salary_type_name': self.salary_type_name or '',
            # 'amount': self.amount_total or 0.0,
        }
        return action
    
    def action_get_data(self):
        rules = []
        lines= []
        for pay in self:
            employee_ids = []
            # if pay.department_id:
            employee_ids = self.env['hr.employee'].search([('department_id','=',pay.department_id.id),('active','=',True)])
            # else:
            #     employee_ids = self.env['hr.employee'].search([('active','=',True)])

            if not pay.line_ids:
                for line in pay.struct_id.line_ids:
                    is_edit =False
                    if line.rule_id.ruleview_type=='edit':
                        is_edit = True
                    rules.append((0,0,{'payroll_rule_id':line.rule_id.id,'show_in_payroll':line.rule_id.show_in_payroll,'decimal_point':line.rule_id.decimal_point,'rulefield_type':line.rule_id.rulefield_type,'sequence':line.sequence,'value':0,'is_edit':is_edit}))
                for employee_id in employee_ids:
                    lines.append((0,0,{'rule_value_ids':rules,'employee_id':employee_id.id}))
                if lines:
                    pay.write({'line_ids':lines})
            else:
                inrules = []
                inemployees = []
                for line in pay.line_ids:
                    if line.employee_id.id not in inemployees:
                        inemployees.append(line.employee_id.id)
                    for rule in line.rule_value_ids:
                        if rule.payroll_rule_id.id not in inrules:
                            inrules.append(rule.payroll_rule_id.id)
                for line in pay.struct_id.line_ids:
                    is_edit =False
                    if line.rule_id.ruleview_type=='edit':
                        is_edit = True

                    rules.append((0,0,{'payroll_rule_id':line.rule_id.id,'show_in_payroll':line.rule_id.show_in_payroll,'decimal_point':line.rule_id.decimal_point,'rulefield_type':line.rule_id.rulefield_type,'sequence':line.sequence,'is_edit':is_edit,'value':0}))	

                for employee_id in employee_ids:
                    if employee_id.id not in inemployees:
                        lines.append((0,0,{'rule_value_ids':rules,'employee_id':employee_id.id}))
                if lines:
                    pay.write({'line_ids':lines})

            self.action_computebyQUERY()
        return {'type': 'ir.actions.client', 'tag': 'reload'}

    def action_computebyQUERY(self):
        self.env.cr.commit()
        query = "select C.id as rule_value_id,D.rule_type as rule_type, D.rulefield_type as rulefield_type, D.value_type as value_type, D.object_type as object_type, \
                    G.id as employee , D.ruleview_type as ruleview_type,D.code as code, B.id as line_id, D.python_code as python_code, F.exp_sequence as exp_sequence, C.is_edited as is_edited\
                    from llp_payroll A inner join llp_payroll_line B ON A.id= B.payroll_id \
                        inner join llp_payroll_rule_value C on B.id=C.line_id \
                        inner join llp_payroll_rule D on D.id=C.payroll_rule_id \
                        inner join llp_payroll_structure E ON E.id= A.struct_id \
                        inner join llp_payroll_structure_line F ON F.struct_id= E.id and F.rule_id=D.id\
                        inner join hr_employee G ON G.id=B.employee_id \
                where A.id=%s group by rule_value_id, rule_type, D.rulefield_type,  value_type, object_type, employee, ruleview_type, code,B.id,\
                    python_code, exp_sequence,is_edited order by F.exp_sequence asc "%(self.id)
        self.env.cr.execute(query)
        dictfetchall = self.env.cr.dictfetchall()

        formulas = {}
        if dictfetchall:
            for dic in dictfetchall:
                group = dic ['exp_sequence'] 
                if group not in formulas:
                    formulas[group] = {
                        'exp_sequence':0,
                        'rules':{},
                    }
                formulas[group]['exp_sequence'] = group
                group1 = dic['code']
                if group1 not in formulas[group]['rules']:
                    formulas[group]['rules'][group1]={
                        'code':'',
                        'python_code':'',
                        'rule_type':'',
                        'value_type':'',
                        'object_type':'',
                        'rulefield_type':'',
                        'employees':{}
                    }
                formulas[group]['rules'][group1]['code'] = group1
                formulas[group]['rules'][group1]['python_code'] = dic['python_code']
                formulas[group]['rules'][group1]['rule_type'] = dic['rule_type']
                formulas[group]['rules'][group1]['object_type'] = dic['object_type']
                formulas[group]['rules'][group1]['value_type'] = dic['value_type']
                formulas[group]['rules'][group1]['rulefield_type'] = dic['rulefield_type']
                group2 = dic['employee']
                if group2 not in formulas[group]['rules'][group1]['employees']:
                    formulas[group]['rules'][group1]['employees'][group2] = {
                        'employee':0,
                        'rule_value_id': 0,
                        'line_id': 0,
                        'is_edited':False,
                    }
                formulas[group]['rules'][group1]['employees'][group2]['employee'] = dic['employee']
                formulas[group]['rules'][group1]['employees'][group2]['rule_value_id'] = dic['rule_value_id']
                formulas[group]['rules'][group1]['employees'][group2]['line_id'] = dic['line_id'] 
                formulas[group]['rules'][group1]['employees'][group2]['is_edited'] = dic['is_edited']

        if formulas:
            for formula in sorted(formulas.values(), key=itemgetter('exp_sequence')):
                for ruled in sorted(formula['rules'].values(), key=itemgetter('code')):
                    for emp in sorted(ruled['employees'].values(), key=itemgetter('employee')):
                        value = None
                        rule = False
                        if emp['rule_value_id']:
                            rule = self.env['llp.payroll.rule.value'].browse(emp['rule_value_id'])	

                        if ruled['rule_type']=='code':
                            value= 0
                            python_code = ruled['python_code']
                            object = {}

                            if ruled['object_type'] == 'contract':
                                object = self.env['hr.contract'].search([('employee_id', '=', emp['employee']),('state','=','open')], limit=1)
                            
                            elif ruled['object_type'] == 'vacation':
                                query = "select B.id from llp_payroll_employee_vacation A inner join llp_payroll_employee_vacation_line B ON A.id=B.vacation_id where A.state = 'done' and B.employee_id = %s and A.month BETWEEN '%s' AND '%s' and A.struct_type='%s'"%(emp['employee'],self.start_date, self.end_date, self.struct_id.struct_type)
                                self.env.cr.execute(query)
                                fetch = self.env.cr.fetchone()

                                if fetch and fetch[0]:
                                    object = self.env['llp.payroll.employee.vacation.line'].browse(fetch[0])

                            elif ruled['object_type'] == 'debt':
                                query = "select A.id from llp_payroll_employee_debt_line A inner join llp_payroll_employee_debt B ON A.debt_id=B.id where B.month BETWEEN '%s' AND '%s' and A.employee_id=%s and B.struct_type='%s' and B.state in ('confirmed')"%(self.start_date, self.end_date,emp['employee'],self.struct_id.struct_type)
                                self.env.cr.execute(query)
                                fetch=self.env.cr.fetchone()

                                if fetch and fetch[0]:
                                    object = self.env['llp.payroll.employee.debt.line'].sudo().browse(fetch[0])	

                            elif ruled['object_type'] == 'attendance':
                                object = {}
                            elif ruled['object_type'] == 'kpi':
                                object = {}

                            if ruled['value_type'] == 'expression':
                                rule_codes = re.findall(r'\b[A-Za-z]+\d+\b',str(python_code))
                                if rule_codes:
                                    where = "where A.line_id = %s "%emp['line_id']
                                    if len(rule_codes) > 1:
                                        where = where + " and B.code in %s"%(str(tuple(rule_codes)))
                                    else:				
                                        where = where + " and B.code = '%s'"%(str(rule_codes[0]))
                                    query="select A.value as value, B.code as code from llp_payroll_rule_value A inner join llp_payroll_rule B ON A.payroll_rule_id = B.id "+where																

                                    self.env.cr.execute(query)
                                    fetchedAll = self.env.cr.dictfetchall()

                                    if fetchedAll:
                                        for fetched in fetchedAll:											
                                            python_code = python_code.replace(fetched['code'],str(fetched['value']))											
                                        
                                        rule_codes = re.findall('n\d+',str(python_code))			
                                        if rule_codes:
                                            for code in rule_codes:
                                                python_code = python_code.replace(code,str(0))

                            # if ruled['rulefield_type']=='from_previous_month':
                            #         value = self.get_from_previous_month(emp['payroll_employee'],python_code,self.start_date, self.end_date)								
                            #         if emp['is_edited']==False:
                            #             self.env.cr.execute("update llp_payroll_rule_value set value=%s where id=%s"%(value,emp['rule_value_id']))

                            try:
                                if rule:
                                    local_dict = {
                                        'rule': rule,
                                        'object': object
                                    }

                                    safe_eval(python_code, local_dict, mode="exec", nocopy=True)
                                    value = local_dict.get('result')
                                else:
                                    value = eval(python_code)

                                if ruled['rulefield_type'] == 'digit':
                                    if not value:
                                        value = 0
                                    if emp['is_edited'] == False:											
                                        self.env.cr.execute('update llp_payroll_rule_value set value = %s where id = %s'%(value,emp['rule_value_id']))
                                elif ruled['rulefield_type'] == 'sign':									
                                    self.env.cr.execute("update llp_payroll_rule_value set char_value = '%s' where id = %s"%(value,emp['rule_value_id']))									
                                
                                self.env.cr.commit()
                            except Exception as e:
                                if ruled['rulefield_type'] == 'digit':																			
                                    self.env.cr.execute('update llp_payroll_rule_value set value = %s where id = %s'%(0,emp['rule_value_id']))
                                elif ruled['rulefield_type'] == 'sign':									
                                    self.env.cr.execute("update llp_payroll_rule_value set char_value = '%s' where id = %s"%(False,emp['rule_value_id']))	
                                pass

    def get_from_previous_month(self,employee_id,code,start_date, end_date):
        value = 0.0
        
        start_date = start_date-relativedelta(months=1)
        end_date = end_date-relativedelta(months=1)

        if end_date:
            query="select C.value as value from llp_payroll A left join llp_payroll_line B ON A.id=B.payroll_id \
            left join llp_payroll_rule_value C on C.line_id = B.id left join llp_payroll_rule D on D.id=C.payroll_rule_id \
            left join llp_payroll_structure E ON E.id= A.struct_id \
            where A.state in ('confirmed','closed') and E.struct_type ='salary_late' and B.payroll_employee_id = %s and D.code ='%s' and A.start_date between '%s' and '%s' and A.end_date between '%s' and '%s' "%(employee_id,code,start_date, end_date)

        # raise UserError(_("%s %s %s ")%(employee_id,code,month_id))
        self.env.cr.execute(query)
        fetch = self.env.cr.fetchone()
        if fetch:			
            value = fetch[0]		
        return value

class LLPPayrollLine(models.Model):
    _name = 'llp.payroll.line'
    _description = "LLP payroll line"
    _order = "name asc"

    name = fields.Char(related="employee_id.name",string="Name", store=True, index=True)
    employee_id = fields.Many2one('hr.employee',string="HR Employee", store=True, index=True)
    payroll_id = fields.Many2one('llp.payroll',string="Payroll", ondelete='cascade', index=True)
    rule_value_ids = fields.One2many('llp.payroll.rule.value','line_id', string="Value")
	
    def action_computebyQUERY(self):
        return

    # Ажилтаны мөр дээрх утга буцаах
    @api.model
    def get_values(self,lines,fields):
        line_ids = []			
        line_ids = self.search([('id','in',lines)])
        line_obj = {}
        for line in line_ids:
            for field in fields:
                if field in line:	
                    if type(line[field]) is str or type(line[field]) is int or type(line[field]) is float:
                        line_obj[field]= line[field]
                    else:
                        line_obj[field]= line[field].id			
        return line_obj

    @api.model
    def get_line_values(self, payroll_id):
        payroll_id = self.env['llp.payroll'].search([('id','=',payroll_id)])
        lines = {}
        employees = []
        rules = [] 
        employee_values = {}
        employee_lines = {}
        is_edits = {}
        is_signs = {}
        decimals = {}
        sum_rules = {}
        
        struct_id = False

        for obj in payroll_id.line_ids:
            line = obj.sudo()
            struct_id = line.payroll_id.struct_id
            employees.append([line.employee_id.id,line.employee_id.name])
            if line.employee_id.id not in employee_values:
                employee_values.update({line.employee_id.id:{}})
                employee_lines.update({line.employee_id.id:{}})
                is_edits.update({line.employee_id.id:{}})
                is_signs.update({line.employee_id.id:{}})
            
            for rule in line.rule_value_ids:
                if [rule.payroll_rule_id.id,rule.payroll_rule_id.name] not in rules:
                    rules.append([rule.payroll_rule_id.id,rule.payroll_rule_id.name])
                    decimals.update({rule.payroll_rule_id.id:rule.payroll_rule_id.decimal_point})
                if rule.payroll_rule_id.id not in employee_values[line.employee_id.id]:
                    
                    is_edits[line.employee_id.id].update({rule.payroll_rule_id.id:rule.is_edit})
                    employee_lines[line.employee_id.id].update({rule.payroll_rule_id.id:rule.id})
                    if rule.payroll_rule_id.id not in sum_rules:
                        sum_rules.update({rule.payroll_rule_id.id:round(rule.value,2)})
                    else:
                        sum_rules[rule.payroll_rule_id.id] = sum_rules[rule.payroll_rule_id.id] +round(rule.value,2)
                    if rule.payroll_rule_id.rulefield_type in ['risk_bonus','digit','bonus','salary_advance','from_previous_month','profit_bonus','monthly_bonus']:
                        employee_values[line.employee_id.id].update({rule.payroll_rule_id.id:rule.value})
                        is_signs[line.employee_id.id].update({rule.payroll_rule_id.id:True})
                    else:
                        employee_values[line.employee_id.id].update({rule.payroll_rule_id.id:rule.char_value})
                        is_signs[line.employee_id.id].update({rule.payroll_rule_id.id:False})

        if struct_id:
            rules = []
            struct_line_ids = self.env['llp.payroll.structure.line'].search([('struct_id','=',struct_id.id)],order='sequence asc')
            for struct in struct_line_ids:
                if struct.rule_id.show_in_payroll:
                    if [struct.rule_id.id,struct.rule_id.name] not in rules:
                        rules.append([struct.rule_id.id,struct.rule_id.name+' '+struct.rule_id.code, bool(struct.rule_id.is_show_sum)])

        lines.update({'employees':employees,'rules':rules,'employee_values':employee_values,'employee_lines':employee_lines,'decimals':decimals,'is_signs':is_signs,'sum_rules':sum_rules,'is_edits':is_edits})
        return lines

class LLPPayrollRuleValue(models.Model):
    _name = 'llp.payroll.rule.value'
    _description = "LLP payroll"
    _order = "create_date desc"

    line_id = fields.Many2one('llp.payroll.line', string="Lines",ondelete='cascade',index=True)
    payroll_rule_id = fields.Many2one('llp.payroll.rule', string="Rule", ondelete='restrict',index=True)
    rulefield_type = fields.Selection([('digit','Digit'),('sign','Sign'),('salary_advance','Salary advance'),('risk_bonus','Bonus'),('bonus','Bonus'),('from_previous_month','Get from previous month'),('profit_bonus','profit bonus'),('monthly_bonus','monthly bonus')], string="Rule field type", default="digit")
    currency_id = fields.Many2one('res.currency', string="Currency")
    value = fields.Monetary(string="Value", currency_field='currency_id', digits=(16, 2))
    char_value = fields.Char(string="Value")
    sequence = fields.Integer(string="Value")
    is_edit = fields.Boolean(string="is_edit")
    is_edited = fields.Boolean(string="Is edited",default=False,index=True)
    attend = fields.Text(string="Formula",index=True)
    decimal_point = fields.Integer(string='Decimal point',index=True)
    show_in_payroll = fields.Boolean(string="Show in payroll Active",default=True,index=True)
    is_show = fields.Boolean(string="Is show" ,default=True,index=True)
    is_sum_view = fields.Boolean(string="Is sum view" ,default=False,index=True)
