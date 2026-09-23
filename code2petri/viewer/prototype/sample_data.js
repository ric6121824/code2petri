/**
 * Phase 2.7 Prototype Sample Data
 * Pre-assembled composite Petri nets with nested inlined functions and compound nodes.
 */

window.PROTOTYPE_SAMPLES = {
  "ecommerce_workflow": {
    "name": "E-Commerce Order Pipeline (Multi-Function Inlined)",
    "description": "Composite workflow featuring two inlined compound functions ('validate_user' and 'calculate_tax'), intermediate AST routing places, and branching.",
    "places": [
      { "id": "p_start", "label": "start", "initial_tokens": 1, "parent": null },
      { "id": "p_routed_0", "label": "p_recv", "initial_tokens": 0, "parent": null },
      
      // Inside compound_validate_user
      { "id": "p_auth_mid", "label": "p_auth_mid", "initial_tokens": 0, "parent": "compound_validate_user" },
      { "id": "p_profile_mid", "label": "p_profile_mid", "initial_tokens": 0, "parent": "compound_validate_user" },
      
      { "id": "p_user_valid", "label": "p_user_valid", "initial_tokens": 0, "parent": null },
      
      // Inside compound_calculate_tax
      { "id": "p_tax_mid", "label": "p_tax_mid", "initial_tokens": 0, "parent": "compound_calculate_tax" },
      
      { "id": "p_order_ready", "label": "p_order_ready", "initial_tokens": 0, "parent": null },
      { "id": "p_charge_ok", "label": "p_charge_ok", "initial_tokens": 0, "parent": null },
      { "id": "p_end", "label": "end", "initial_tokens": 0, "parent": null }
    ],
    "transitions": [
      { "id": "t_recv", "label": "receive_order()", "tau": 1.0, "parent": null, "line_number": 12 },
      
      // Inside compound_validate_user
      { "id": "t_v1", "label": "check_auth_token()", "tau": 1.0, "parent": "compound_validate_user", "line_number": 45 },
      { "id": "t_v2", "label": "fetch_user_db()", "tau": 1.0, "parent": "compound_validate_user", "line_number": 46 },
      { "id": "t_v3", "label": "verify_account_status()", "tau": 1.0, "parent": "compound_validate_user", "line_number": 47 },
      
      // Inside compound_calculate_tax
      { "id": "t_t1", "label": "lookup_jurisdiction()", "tau": 1.0, "parent": "compound_calculate_tax", "line_number": 88 },
      { "id": "t_t2", "label": "apply_vat_rate()", "tau": 1.0, "parent": "compound_calculate_tax", "line_number": 89 },
      
      { "id": "t_charge", "label": "charge_credit_card()", "tau": 1.0, "parent": null, "line_number": 18 },
      { "id": "t_notify", "label": "send_order_confirmation()", "tau": 1.0, "parent": null, "line_number": 19 }
    ],
    "compounds": [
      { "id": "compound_validate_user", "label": "validate_user()", "function_name": "validate_user", "file": "auth_service.py" },
      { "id": "compound_calculate_tax", "label": "calculate_tax()", "function_name": "calculate_tax", "file": "tax_service.py" }
    ],
    "arcs": [
      { "source": "p_start", "target": "t_recv", "weight": 1 },
      { "source": "t_recv", "target": "p_routed_0", "weight": 1 },
      
      // Entry to compound_validate_user
      { "source": "p_routed_0", "target": "t_v1", "weight": 1 },
      { "source": "t_v1", "target": "p_auth_mid", "weight": 1 },
      { "source": "p_auth_mid", "target": "t_v2", "weight": 1 },
      { "source": "t_v2", "target": "p_profile_mid", "weight": 1 },
      { "source": "p_profile_mid", "target": "t_v3", "weight": 1 },
      // Exit from compound_validate_user
      { "source": "t_v3", "target": "p_user_valid", "weight": 1 },
      
      // Entry to compound_calculate_tax
      { "source": "p_user_valid", "target": "t_t1", "weight": 1 },
      { "source": "t_t1", "target": "p_tax_mid", "weight": 1 },
      { "source": "p_tax_mid", "target": "t_t2", "weight": 1 },
      // Exit from compound_calculate_tax
      { "source": "t_t2", "target": "p_order_ready", "weight": 1 },
      
      { "source": "p_order_ready", "target": "t_charge", "weight": 1 },
      { "source": "t_charge", "target": "p_charge_ok", "weight": 1 },
      { "source": "p_charge_ok", "target": "t_notify", "weight": 1 },
      { "source": "t_notify", "target": "p_end", "weight": 1 }
    ]
  },
  
  "python_mixed_pipeline": {
    "name": "Python mixed_pipeline_func (AST Generated)",
    "description": "Actual control flow Petri net from tests/test_code/petri_py/mixed_pipeline.py with inlined helper_calc.",
    "places": [
      { "id": "p0", "label": "start", "initial_tokens": 1, "parent": null },
      { "id": "p1", "label": "p1", "initial_tokens": 0, "parent": null },
      { "id": "p2", "label": "p2", "initial_tokens": 0, "parent": null },
      { "id": "p3", "label": "exit_t3", "initial_tokens": 0, "parent": null },
      { "id": "p4", "label": "p4", "initial_tokens": 0, "parent": null },
      { "id": "p5", "label": "p5", "initial_tokens": 0, "parent": null },
      
      // Inlined helper_calc
      { "id": "p_helper_mid", "label": "p_calc_mid", "initial_tokens": 0, "parent": "compound_helper_calc" },
      
      { "id": "p6", "label": "p6", "initial_tokens": 0, "parent": null },
      { "id": "p7", "label": "except_entry", "initial_tokens": 0, "parent": null },
      { "id": "p10", "label": "p10", "initial_tokens": 0, "parent": null },
      { "id": "p9", "label": "finally_entry", "initial_tokens": 0, "parent": null },
      { "id": "p8", "label": "try_exit", "initial_tokens": 0, "parent": null },
      { "id": "p_end", "label": "end", "initial_tokens": 0, "parent": null }
    ],
    "transitions": [
      { "id": "t1", "label": "total = 0", "tau": 1.0, "line_number": 6, "parent": null },
      { "id": "t2", "label": "items = [1, 2, 3]", "tau": 1.0, "line_number": 7, "parent": null },
      { "id": "t3", "label": "for item in items", "tau": 1.0, "line_number": 9, "parent": null },
      { "id": "t4", "label": "exit", "tau": 1.0, "line_number": 9, "parent": null },
      { "id": "t5", "label": "if item > 1", "tau": 1.0, "line_number": 10, "parent": null },
      { "id": "t6", "label": "else", "tau": 1.0, "line_number": 13, "parent": null },
      
      // Inside helper_calc compound
      { "id": "t_helper_entry", "label": "arg val = item", "tau": 1.0, "line_number": 1, "parent": "compound_helper_calc" },
      { "id": "t_helper_exec", "label": "return val * 2", "tau": 1.0, "line_number": 2, "parent": "compound_helper_calc" },
      
      { "id": "t8", "label": "total += 1", "tau": 1.0, "line_number": 13, "parent": null },
      { "id": "t9", "label": "final_res = total / 2", "tau": 1.0, "line_number": 16, "parent": null },
      { "id": "t10", "label": "except ZeroDivisionError", "tau": 1.0, "line_number": 17, "parent": null },
      { "id": "t11", "label": "final_res = -1", "tau": 1.0, "line_number": 18, "parent": null },
      { "id": "t12", "label": "final_res += 10", "tau": 1.0, "line_number": 20, "parent": null },
      { "id": "t13", "label": "return final_res", "tau": 1.0, "line_number": 22, "parent": null }
    ],
    "compounds": [
      { "id": "compound_helper_calc", "label": "helper_calc(item)", "function_name": "helper_calc", "file": "mixed_pipeline.py" }
    ],
    "arcs": [
      { "source": "p0", "target": "t1", "weight": 1 },
      { "source": "t1", "target": "p1", "weight": 1 },
      { "source": "p1", "target": "t2", "weight": 1 },
      { "source": "t2", "target": "p2", "weight": 1 },
      { "source": "p2", "target": "t3", "weight": 1 },
      { "source": "p2", "target": "t4", "weight": 1 },
      
      // Loop body vs exit
      { "source": "t3", "target": "p4", "weight": 1 },
      { "source": "t4", "target": "p3", "weight": 1 },
      
      // Branching: if / else
      { "source": "p4", "target": "t5", "weight": 1 },
      { "source": "p4", "target": "t6", "weight": 1 },
      
      // If branch into inlined helper_calc
      { "source": "t5", "target": "p5", "weight": 1 },
      { "source": "p5", "target": "t_helper_entry", "weight": 1 },
      { "source": "t_helper_entry", "target": "p_helper_mid", "weight": 1 },
      { "source": "p_helper_mid", "target": "t_helper_exec", "weight": 1 },
      { "source": "t_helper_exec", "target": "p2", "weight": 1 },
      
      // Else branch
      { "source": "t6", "target": "p6", "weight": 1 },
      { "source": "p6", "target": "t8", "weight": 1 },
      { "source": "t8", "target": "p2", "weight": 1 },
      
      // After loop exit -> Try / Except / Finally
      { "source": "p3", "target": "t9", "weight": 1 },
      { "source": "t9", "target": "p7", "weight": 1 },
      { "source": "t9", "target": "p9", "weight": 1 },
      { "source": "p7", "target": "t10", "weight": 1 },
      { "source": "t10", "target": "p10", "weight": 1 },
      { "source": "p10", "target": "t11", "weight": 1 },
      { "source": "t11", "target": "p9", "weight": 1 },
      { "source": "p9", "target": "t12", "weight": 1 },
      { "source": "t12", "target": "p8", "weight": 1 },
      { "source": "p8", "target": "t13", "weight": 1 },
      { "source": "t13", "target": "p_end", "weight": 1 }
    ]
  }
};
