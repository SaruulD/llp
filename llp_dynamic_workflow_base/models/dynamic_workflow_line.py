
from odoo import api, fields, models, _
from odoo.exceptions import UserError

SELECTION_CONFIRM_BY = [
    ('by_user', 'By User'), 
    ('by_group', 'By Group'), 
    ('by_created', 'By Created User'), 
    ('by_manager', 'By Manager'),
    ('by_job', 'By Jobs'),
    ]

class DynamicWorkflowLines(models.Model):
    _name = 'dynamic.workflow.line'
    _description = 'Dynamic Workflow Line'
    _rec_name = 'state'
    _order = 'sequence'

    flow_id = fields.Many2one('dynamic.workflow', 'Flow')
    state_id = fields.Many2one('dynamic.state', 'Dynamic state', domain="[('is_dynamic', '=', True)]")
    state = fields.Char(related='state_id.state', readonly=False)
    name = fields.Char(related='state_id.name')
    is_active = fields.Boolean('Is active', default=True)
    confirm_by = fields.Selection(SELECTION_CONFIRM_BY, 'Confirm by', default="by_user")
    user_ids = fields.Many2many('res.users', string='Users')
    group_ids = fields.Many2many('res.groups', string='Groups')
    job_ids = fields.Many2many('hr.job', string='Jobs')
    model_states = fields.Many2many('dynamic.state', compute='_compute_model_states', string='Model States')
    model_state = fields.Many2one('dynamic.state', 'Model State', domain="[('id','in',model_states)]")
    sequence = fields.Integer('Sequence',compute='_compute_sequence',store=True,readonly=False)
    is_super = fields.Boolean("Is super", help="If enabled, the workflow will be cancelled when the proposal is rejected")
    is_external = fields.Boolean("Is External", help="If the approver will not approve in Odoo ERP but will approve elsewhere")
    send_notif = fields.Boolean('Send notification', help='Whether to send notifications to the approval persons')

    deputy_user_email = fields.Char('Deputy mail', help='Email of the deputy approver')


    # Ашиглагдсан workflow мөр байвал устгах эсвэл идэвхгүй болгохыг хориглох
    def _check_if_used(self):
        self.ensure_one()  # Зөвхөн нэг мөрөнд ажиллана
        
        # Model байгаа эсэхийг шалгах
        if not self.flow_id or not self.flow_id.model_id:
            return
        
        model = self.flow_id.model_id
        model_name = model.model
        field_name = 'line_state'
        
        # Тухайн field model-д байгаа эсэхийг шалгах
        if field_name not in model.field_id.mapped('name'):
            return
        
        # Бүртгэлийн ID-г авах (шинэ болон хуучин бүртгэлд ажиллана)
        self_id = self.id or (self._origin.id if hasattr(self._origin, 'id') else None)
        if not self_id:
            return
        
        # Тухайн state-ийг ашиглаж буй бүртгэлүүдийг хайх
        used_records = self.env[model_name].search([
            (field_name, '=', self_id)
        ], limit=1)  # Ганцхан бүртгэл олоход л хангалттай
        
        if used_records:
            raise UserError(_('You cannot delete or disable.\nState Line is used in %s with %s id',model.name,used_records.ids))
            
    @api.onchange('is_active')
    def _onchange_is_active(self):
        for rec in self:
            if not rec.is_active:
                rec._check_if_used()

    def unlink(self):
        for rec in self:
            rec._check_if_used()
        return super().unlink()
    
    @api.depends('flow_id')
    def _compute_sequence(self):
        for rec in self:
            if rec.flow_id:
                seq = [line.sequence for line in rec.flow_id.line_ids]
                max_seq = max(seq) if seq else 0
                sequence = max_seq + 1
                rec.sequence = sequence

    def _get_deputy_user_record(self):
        mail = self.deputy_user_email
        if mail:
            internal_user = self.env['res.users'].sudo().search([('login','=',mail)],limit=1)
            if internal_user:
                return 'internal',internal_user
            return False, False
        return False, False

    #Одоо нэвтэрсэн хэрэглэгчид үйлдэл хийх эрх байгаа эсэх
    def _check_user_access(self,created_user_id = False):
        self.ensure_one()
        is_internal, user_id = self._get_deputy_user_record()
        if is_internal == 'internal':
            return self.env.user == user_id
        elif is_internal == 'external':
            return False
        user_match = False
        if self.confirm_by == 'by_user':
            if self.env.user.id in self.user_ids.ids or not self.user_ids:
                user_match = True
        elif self.confirm_by == 'by_group':
            if set(self.group_ids.ids) & set(self.env.user.groups_id.ids) or not self.group_ids:
                user_match = True
        elif self.confirm_by == 'by_manager' and created_user_id:
            if created_user_id.employee_id.parent_id.user_id.id == self.env.user.id:
                user_match = True
        elif self.confirm_by == 'by_job':
            if self.env.user.employee_id.job_id.id in self.job_ids.ids or not self.job_ids.ids:
                user_match = True
        elif self.confirm_by =='by_created' and created_user_id:
            if created_user_id.id == self.env.user.id:
                user_match = True
        if self.is_external:
            return False
        return user_match

    #Тус мөр дээр батлахаар хүлээгдэж буй хэрэглэгчдийг бүгдийг авах
    def _get_users_waiting(self, created_user_id = False):
        self.ensure_one()
        is_internal, user_id = self._get_deputy_user_record()
        if is_internal == 'internal':
            return user_id.ids
        elif is_internal == 'external':
            return []
        if self.is_external:
            return []
        waiting_user_ids = []
        if self.confirm_by == "by_user" and self.user_ids:
            for id in self.user_ids.ids:
                waiting_user_ids.append(id)
        elif self.confirm_by == "by_group" and self.group_ids:
            # user_ids = []
            for group_id in self.group_ids:
                for user_id in group_id.users:
                    # dawhtssan bol oruulahgui
                    if not user_id.id in waiting_user_ids:
                        waiting_user_ids.append(user_id.id)

        elif self.confirm_by == 'by_manager' and created_user_id:
            if created_user_id.sudo().employee_id.parent_id.user_id.id:
                waiting_user_ids.append(created_user_id.sudo().employee_id.parent_id.user_id.id)

        elif self.confirm_by == 'by_created' and created_user_id:
            waiting_user_ids.append(created_user_id.id)

        elif self.confirm_by == 'by_job':
            employees = self.env['hr.employee'].search([('job_id','in',self.job_ids.ids)])
            waiting_user_ids = employees.user_id.ids
        
        return waiting_user_ids
    
    @api.model_create_multi
    def create(self, vals_list):
        res = super().create(vals_list)
        for record in res:
            if record:
                self.env['line.dynamic.state'].create({
                    'dynamic_state': record.state_id.id,
                    'workflow_line_id': record.id,
                    'sequence': record.sequence
                })
        return res

    def write(self, vals):
        if 'sequence' in vals:
            state = self.env['line.dynamic.state'].search([('dynamic_state', '=', self.state_id.id), ('workflow_line_id', '=', self.id)])
            state.update({'sequence': vals['sequence']})
        return super(DynamicWorkflowLines, self).write(vals)
    
    @api.depends('flow_id.model_id')
    def _compute_model_states(self):
        for record in self:
            if not record.flow_id.model_id:
                record.model_states = False
                continue
            try:
                lines = []
                stat = self.env[record.flow_id.model_id.model]._fields['state'].selection
                for st in stat:
                    created_states = self.env['dynamic.state'].search([('state', '=', st[0]), ('name', '=', st[1])])
                    if not created_states:
                        created_states = self.env['dynamic.state'].create({'state': st[0],
                                                                        'name': st[1],
                                                                        'is_dynamic': False})
                    lines.append(created_states.id)
                record.model_states = lines
            except:
                record.model_states = False

    def _approve(self,created_user_id = False,id = False, name=False, model=False, model_description=False,no_access = False):
        next_line = self._get_next_line_state(self.sequence)
        #шалгахгүй
        if no_access:
            if next_line:
                next_line._send_notif(id, name, model, model_description)
            return next_line
        
        if self._check_user_access(created_user_id):
            if next_line:
                next_line._send_notif(id, name, model, model_description)
            return next_line
        else:
            raise UserError('Танд энэ үйлдлийг хийх эрх байхгүй байна.')
        
    def _get_prev_line_state(self,current_seq):
        #Super бол буцаах үед эхлүүлэх
        if self.is_super:
            return False
        matching_objects = [obj for obj in self.flow_id.active_line_ids if obj.sequence < current_seq]
        if matching_objects:
            prev_line = max(matching_objects, key=lambda obj: obj.sequence)
            return prev_line
        else:
            return False
    
    def _get_next_line_state(self, current_seq):
        matching_objects = [obj for obj in self.flow_id.active_line_ids if obj.sequence > current_seq]
        if matching_objects:
            next_line = min(matching_objects, key=lambda obj: obj.sequence)
            return next_line
        else:
            return False
        
    def _return(self,created_user_id = False,id = False, name=False, model=False, model_description=False,no_access = False):
        prev_line = self._get_prev_line_state(self.sequence)
        if no_access:
            if prev_line:
                prev_line._send_notif(id, name, model, model_description)   #notif ywulah
            return prev_line
        
        if self._check_user_access(created_user_id):
            if prev_line:
                prev_line._send_notif(id, name, model, model_description)   #notif ywulah
            return prev_line
        else:
            raise UserError('Танд энэ үйлдлийг хийх эрх байхгүй байна.')

    def name_get(self):
        result = []
        for record in self:
            name = record.state_id.name
            result.append((record.id, name))
        return result
    
    def _send_notif(self,id,name,model,model_description):
        if self.send_notif:
            self.__send_notif(id,name,model,model_description)
            

    def __send_notif(self,id,name,model,model_description):
        waiting_user_id = self._get_users_waiting()
        base_url = self.env['ir.config_parameter'].sudo().get_param('web.base.url')
        url = f'{base_url}/web#id={id}&model={model}&view_type=form'
        for rec in waiting_user_id:

            #send message in odoo
            user_id = self.env['res.users'].browse(rec)
            html = f'''
                    <b>Батлах урсгал</b> <br/>
                    Тань дээр батлах урсгалаар батлуулж буй <a target="_blank" href="{url}">
                    <b>{name}</b></a> дугаартай {model_description} хүлээгдэж байна. <br/>Та линкээр дамжин үйлдлийг хийнэ үү.
                '''
            self._action_send_message(user_id,html)
        
    def _action_send_message(self,partner_id,html_text):
        user_id = self.env["res.users"].browse(1)   #odoo bot

        # chat_channel = self.env["mail.channel"].search([("name","ilike",str(user_id.partner_id.name)),("name","ilike",str(partner_id.partner_id.name))],limit=1)
        query = "SELECT id FROM mail_channel WHERE name ilike '%"+str(user_id.partner_id.name)+"%' and name ilike '%"+str(partner_id.partner_id.name)+"%';"
        self._cr.execute(query)
        chat_channel = self._cr.dictfetchall()
        # Create a new mail channel for the chat if not exists
        
        if len(chat_channel) == 0:
            chat_channel = self.env['mail.channel'].with_user(user_id).create({
                'name': str(partner_id.partner_id.name+', '+user_id.partner_id.name),
                'channel_partner_ids': [(4, partner_id.partner_id.id), (4, user_id.partner_id.id)],
                'channel_type': 'chat',
            })
        else:
            chat_channel = self.env["mail.channel"].browse(chat_channel[0]["id"])
        chat_channel.sudo().message_post(author_id=user_id.partner_id.id,
                                         body=html_text,
                                         message_type='comment',
                                         subtype_xmlid="mail.mt_comment",
                                         )