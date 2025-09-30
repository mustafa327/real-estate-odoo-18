from odoo import models, fields, api, _
from odoo.exceptions import ValidationError
from odoo import _, fields

class RentContract(models.Model):
    _name = 'rent.contract'
    _description = 'Rent Contract'
    _inherit = ['mail.thread', 'mail.activity.mixin']

    name = fields.Char(string='العقد', compute='_compute_name', store=True)

    partner_id = fields.Many2one('res.partner', string='المستأجر', required=True, tracking=True)
    building_id = fields.Many2one('estate.building', string='البناية', required=True, tracking=True)
    unit_id = fields.Many2one('estate.building.unit', string='الوحدة/الشقة', required=True, domain="[('building_id','=',building_id)]", tracking=True)

    company_id = fields.Many2one('res.company', string='الشركة', default=lambda self: self.env.company, required=True)
    currency_id = fields.Many2one(related='company_id.currency_id', store=True, readonly=True)

    responsible_id = fields.Many2one( 'res.users', string='Responsible', default=lambda self: self.env.user, tracking=True, help="User who will receive the payment reminder activity.")
    rent_due_day = fields.Integer(string='Rent Due Day', default=1, tracking=True, help='Day of month the rent is due (1..31).')
    last_due_activity_date = fields.Date(string='Last Due Activity', readonly=True)

    amount = fields.Monetary(string='مبلغ الإيجار', required=True)
    recurrence = fields.Selection([('month', 'شهري'), ('year', 'سنوي')], string='دورية الدفع', default='month', required=True)

    start_date = fields.Date(string='تاريخ البداية', required=True)
    end_date = fields.Date(string='تاريخ النهاية')

    state = fields.Selection([
        ('draft', 'مسودة'),
        ('active', 'فعّال'),
        ('expired', 'منتهي'),
        ('cancelled', 'ملغى')
    ], default='draft', tracking=True)

    monthly_amount = fields.Monetary(compute='_compute_normalized', string='شهريًا', store=False)
    yearly_amount = fields.Monetary(compute='_compute_normalized', string='سنويًا', store=False)

    invoice_count = fields.Integer(compute='_compute_invoice_count')

    @api.depends('partner_id', 'building_id', 'unit_id')
    def _compute_name(self):
        for rec in self:
            parts = []
            if rec.building_id: parts.append(rec.building_id.name)
            if rec.unit_id: parts.append(rec.unit_id.unit_number or rec.unit_id.name)
            if rec.partner_id: parts.append(rec.partner_id.display_name)
            rec.name = ' - '.join(parts) or _('Rent Contract')

    @api.depends('amount', 'recurrence')
    def _compute_normalized(self):
        for rec in self:
            if rec.recurrence == 'month':
                rec.monthly_amount = rec.amount
                rec.yearly_amount = rec.amount * 12.0
            else:
                rec.monthly_amount = rec.amount / 12.0
                rec.yearly_amount = rec.amount

    _sql_constraints = [
        ('contract_unique_active', 'unique(unit_id, state)', 'لا يمكن أن تكون هناك أكثر من عقد فعّال لنفس الوحدة.'),
    ]

    def action_set_active(self):
        for rec in self:
            rec.state = 'active'
            rec.unit_id.tenant_id = rec.partner_id

    def action_set_expired(self):
        self.write({'state': 'expired'})

    def action_cancel(self):
        self.write({'state': 'cancelled'})

    def _prepare_invoice_vals(self):
        self.ensure_one()

        # Use company context (v18) — don't filter on company_id in the domain
        Account = self.env['account.account'].with_company(self.company_id)

        # v18 uses `account_type` (fallback to internal_group just in case)
        income_account = Account.search([('account_type', '=', 'income')], limit=1)
        if not income_account:
            income_account = Account.search([('internal_group', '=', 'income')], limit=1)

        if not income_account:
            raise ValidationError(_(
                "No income account found for company %s. "
                "Please create an Account with account_type='income'."
            ) % (self.company_id.display_name,))

        return {
            'move_type': 'out_invoice',
            'partner_id': self.partner_id.id,
            'company_id': self.company_id.id,
            'invoice_date': fields.Date.context_today(self),
            'currency_id': self.currency_id.id,
            # GL tagging
            'x_building_id': self.building_id.id,
            'x_unit_id': self.unit_id.id,
            'x_floor': self.unit_id.floor,
            'x_unit_number': self.unit_id.unit_number,
            'invoice_line_ids': [
                (0, 0, {
                    'name': self.name,
                    'quantity': 1.0,
                    'price_unit': self.amount if self.recurrence == 'month' else (self.amount / 12.0),
                    'account_id': income_account.id,
                })
            ],
        }

    def action_create_invoice(self):
        moves = self.env['account.move']
        for rec in self:
            mv = self.env['account.move'].create(rec._prepare_invoice_vals())
            moves |= mv
        # Open the invoices we just created with explicit v18 view_mode
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',
            'domain': [('id', 'in', moves.ids)],
            'context': {'default_move_type': 'out_invoice'},
        }

    def _compute_invoice_count(self):
        for rec in self:
            rec.invoice_count = self.env['account.move'].search_count([
                ('move_type', '=', 'out_invoice'), ('partner_id', '=', rec.partner_id.id), ('x_building_id', '=', rec.building_id.id), ('x_unit_id', '=', rec.unit_id.id)
            ])

    def action_view_invoices(self):
        self.ensure_one()
        return {
            'type': 'ir.actions.act_window',
            'name': _('Invoices'),
            'res_model': 'account.move',
            'view_mode': 'list,form',  # <-- was 'tree,form'
            'domain': [
                ('move_type', '=', 'out_invoice'),
                ('partner_id', '=', self.partner_id.id),
                ('x_building_id', '=', self.building_id.id),
                ('x_unit_id', '=', self.unit_id.id),
            ],
        }


    @api.constrains('rent_due_day')
    def _check_rent_due_day(self):
        for rec in self:
            if not (1 <= rec.rent_due_day <= 31):
                raise ValidationError(_("Rent Due Day must be between 1 and 31."))

    # === CRON ENTRYPOINT ===
    @api.model
    def cron_create_rent_due_activities(self):
        """Daily: create a TODO activity on contracts due today (once per day)."""
        today = fields.Date.context_today(self)
        # active contracts, valid dates, due today, and not already reminded today
        domain = [
            ('state', '=', 'active'),
            '|', ('start_date', '=', False), ('start_date', '<=', today),
            '|', ('end_date', '=', False), ('end_date', '>=', today),
            ('rent_due_day', '=', today.day),
            '|', ('last_due_activity_date', '=', False), ('last_due_activity_date', '<', today),
        ]
        contracts = self.search(domain)
        if not contracts:
            return

        todo_type = self.env.ref('mail.mail_activity_data_todo')
        for c in contracts:
            c.activity_schedule(
                activity_type_id=todo_type.id,
                date_deadline=today,
                user_id=c.responsible_id.id or self.env.user.id,
                summary=_('Pay Rent'),
                note=_('Rent is due today for %s — %s / %s.') % (
                    c.partner_id.display_name,
                    c.building_id.name or '',
                    (c.unit_id.unit_number or c.unit_id.display_name or '')
                ),
            )
            c.last_due_activity_date = today