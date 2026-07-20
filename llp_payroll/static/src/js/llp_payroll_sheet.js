/** @odoo-module */

import { Component, onWillStart, onWillUpdateProps } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { standardFieldProps } from "@web/views/fields/standard_field_props";

class PayrollSheetField extends Component {
  static template = "llp_payroll.PayrollSheetField";
  static props = { ...standardFieldProps };
  static supportedTypes = ["one2many"];

  setup() {
    this.orm = useService("orm");
    this.action = useService("action");
    this.formatMoney = (val, rule, decimals) => {
      if (rule[3] !== "digit" && rule[3] !== "from_previous_payroll") {
        return val === false ? "" : val ?? "";
      }
      if (typeof val === "string") {
        const maybeNum = Number(val);
        if (!isNaN(maybeNum) && val.trim() !== "") {
          return maybeNum.toLocaleString(undefined, {
            minimumFractionDigits: decimals,
            maximumFractionDigits: decimals,
          });
        }
        return val;
      }

      if (typeof val === "number" && !isNaN(val)) {
        const n = Number(val) || 0;
        return n.toLocaleString(undefined, {
          minimumFractionDigits: decimals,
          maximumFractionDigits: decimals,
        });
      }

      return val ?? "";
    };

    this.goToEmployee = this.goToEmployee.bind(this);
    this.goToRule = this.goToRule.bind(this);
    this.onValueChange = this.onValueChange.bind(this);

    this.state = {
      employees: [],
      rules: [],
      employee_values: {},
      employee_lines: {},
    };

    this.loadData = this.loadData.bind(this);

    onWillStart(async () => {
      await this.loadData(this.props.record?.resId);
    });

    onWillUpdateProps(async (nextProps) => {
      const nextId = nextProps.record?.resId;
      if (nextId !== this.props.record?.resId) {
        await this.loadData(nextId);
      }
    });
  }

  async loadData(sheetId) {
    // Pager-ээр шинэ bичлэг рүү орох эсвэл шинэ (unsaved) bичлэг дээр байх үед
    // хуучин утгыг цэвэрлэнэ, ингэснээр солигдох хооронд хуучин өгөгдөл харагдахгүй
    this.state.employees = [];
    this.state.rules = [];
    this.state.employee_values = {};
    this.state.employee_lines = {};

    if (!sheetId) return;

    const data = await this.orm.call("llp.payroll.line", "get_line_values", [
      sheetId,
    ]);
    Object.assign(this.state, data);
  }

  onValueChange(ev, ruleValueId, empId, ruleId) {
    const raw = ev.target.value;

    const sheetState = this.props.record.data.state;

    // Update UI first
    if (!this.state.employee_values[empId]) {
      this.state.employee_values[empId] = {};
    }

    const numeric = Number(raw) || 0;
    this.state.employee_values[empId][ruleId] = numeric;

    // 🔄 RERENDER UI, totals will recompute automatically
    this.render();

    this.orm.call("llp.payroll.line", "update_value", [ruleValueId, raw]);
  }

  goToEmployee(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "hr.employee",
      res_id: id,
      views: [[false, "form"]],
    });
  }
  goToRule(id) {
    this.action.doAction({
      type: "ir.actions.act_window",
      res_model: "llp.payroll.rule",
      res_id: id,
      views: [[false, "form"]],
    });
  }
}

registry.category("fields").add("payroll_sheet", {
  component: PayrollSheetField,
  supportedTypes: ["one2many"],
});