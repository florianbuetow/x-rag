# Clean Code & Clean Architecture: A Comprehensive Guide for Coding Agents

<!-- DOCUMENT_META
domain: order_processing_ecommerce_backend
language: python_vanilla
style: pep8_google
version: 1.0
-->

## How to Use This Guide

This guide is designed for **coding agents** to reference when writing or reviewing Python code. Each principle follows a consistent format:

1. **Summary**: What the principle means
2. **Anti-Pattern**: Code that violates the principle (marked `<!-- ANTI_PATTERN -->`)
3. **Refactored**: Cleaned code applying the principle (marked `<!-- REFACTORED -->`)
4. **Key Takeaways**: Quick rules to remember

### Marker Reference

| Marker | Meaning |
|--------|---------|
| `<!-- PRINCIPLE: name -->` | Start of principle section |
| `<!-- ANTI_PATTERN -->` | Bad code example follows |
| `<!-- REFACTORED -->` | Clean code example follows |
| `<!-- END_PRINCIPLE -->` | End of principle section |
| `<!-- MULTI_FILE_EXAMPLE -->` | Multi-file architecture example |

### Domain Context

All examples use an **order processing backend** with these core concepts:
- `Order`: A customer purchase with items, totals, status
- `Customer`: User placing orders
- `Product`: Items being sold
- `Payment`: Payment processing
- `Inventory`: Stock management
- `Notification`: Email/SMS alerts

---

# Part 1: Naming

<!-- PRINCIPLE: intention_revealing_names -->
## 1.1 Intention-Revealing Names

### Summary
Names should reveal intent. A reader should understand what a variable holds or what a function does without needing additional context.

<!-- ANTI_PATTERN -->
```python
# Bad: What is d? What does process do?
def process(d):
    for i in d:
        if i['s'] == 1:
            i['s'] = 2
    return d
```

<!-- REFACTORED -->
```python
# Good: Clear intent in every name
def mark_orders_as_shipped(orders: list[dict]) -> list[dict]:
    for order in orders:
        if order['status'] == OrderStatus.PAID:
            order['status'] = OrderStatus.SHIPPED
    return orders
```

### Key Takeaways
- If a name requires a comment to explain it, the name is wrong
- Longer descriptive names beat short cryptic ones
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: avoid_disinformation -->
## 1.2 Avoid Disinformation

### Summary
Don't use names that mislead. Don't call something a "list" if it's not a list. Don't use names that vary in small ways.

<!-- ANTI_PATTERN -->
```python
# Bad: order_list is a dict, not a list
order_list = {'ORD001': Order(), 'ORD002': Order()}

# Bad: Too similar, easy to confuse
orders_for_processing = []
orders_for_processsing = []  # Typo that compiles
```

<!-- REFACTORED -->
```python
# Good: Name matches type
orders_by_id = {'ORD001': Order(), 'ORD002': Order()}

# Good: Distinct, meaningful names
pending_orders = []
processed_orders = []
```

### Key Takeaways
- Name should match the actual data structure
- Avoid names that differ only slightly
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: meaningful_distinctions -->
## 1.3 Meaningful Distinctions

### Summary
If names must be different, they should mean something different. Avoid noise words like `data`, `info`, `the`, `a`.

<!-- ANTI_PATTERN -->
```python
# Bad: What's the difference?
def get_order(order_id): ...
def get_order_data(order_id): ...
def get_order_info(order_id): ...

# Bad: Noise words
the_order = Order()
order_data = Order()
```

<!-- REFACTORED -->
```python
# Good: Each name has distinct meaning
def get_order(order_id) -> Order: ...
def get_order_summary(order_id) -> OrderSummary: ...
def get_order_history(order_id) -> list[OrderEvent]: ...

# Good: Just use the noun
order = Order()
```

### Key Takeaways
- Number series (a1, a2) are meaningless—avoid them
- Noise words are redundant—remove them
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: pronounceable_searchable_names -->
## 1.4 Pronounceable and Searchable Names

### Summary
Use names you can speak aloud. Single-letter names and magic numbers are impossible to search.

<!-- ANTI_PATTERN -->
```python
# Bad: Unpronounceable, unsearchable
def calc_ord_ttl(o):
    t = 0
    for i in o.itms:
        t += i.p * i.q
    if t > 100:
        t = t * 0.9
    return t
```

<!-- REFACTORED -->
```python
# Good: Pronounceable, searchable
BULK_DISCOUNT_THRESHOLD = 100
BULK_DISCOUNT_RATE = 0.9

def calculate_order_total(order: Order) -> float:
    total = 0
    for item in order.items:
        total += item.price * item.quantity
    if total > BULK_DISCOUNT_THRESHOLD:
        total = total * BULK_DISCOUNT_RATE
    return total
```

### Key Takeaways
- Extract magic numbers to named constants
- Use full words, not abbreviations
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: class_function_naming -->
## 1.5 Class Names vs Function Names

### Summary
Classes are nouns. Functions are verbs. Avoid vague names like `Manager`, `Processor`, `Data`, `Info`.

<!-- ANTI_PATTERN -->
```python
# Bad: Class as verb, vague "Manager"
class ProcessOrder:
    def order(self): ...

class OrderManager:  # What does it manage?
    def do(self, order): ...
```

<!-- REFACTORED -->
```python
# Good: Class is noun, methods are verbs
class Order:
    def calculate_total(self) -> float: ...
    def add_item(self, item: OrderItem) -> None: ...

class OrderRepository:  # Clear: it stores/retrieves orders
    def save(self, order: Order) -> None: ...
    def find_by_id(self, order_id: str) -> Order: ...
```

### Key Takeaways
- Class names: `Order`, `Customer`, `PaymentGateway` (nouns)
- Method names: `save`, `delete`, `calculate_total` (verbs)
- Avoid: `Manager`, `Processor`, `Handler` unless specific
<!-- END_PRINCIPLE -->

---

# Part 2: Functions

<!-- PRINCIPLE: small_functions -->
## 2.1 Small Functions

### Summary
Functions should be small. 20 lines is a reasonable upper bound. If a function is doing too much, extract smaller functions.

<!-- ANTI_PATTERN -->
```python
# Bad: Function doing too many things
def process_order(order_id, customer_email):
    order = db.query(f"SELECT * FROM orders WHERE id = '{order_id}'")
    if not order:
        return {"error": "Order not found"}
    total = 0
    for item in order.items:
        product = db.query(f"SELECT * FROM products WHERE id = '{item.product_id}'")
        if product.stock < item.quantity:
            return {"error": f"Insufficient stock for {product.name}"}
        total += product.price * item.quantity
        db.execute(f"UPDATE products SET stock = stock - {item.quantity}")
    if total > 100:
        total = total * 0.9
    order.total = total
    order.status = "confirmed"
    db.execute(f"UPDATE orders SET total = {total}, status = 'confirmed'")
    send_email(customer_email, f"Order confirmed: ${total}")
    return {"success": True, "total": total}
```

<!-- REFACTORED -->
```python
# Good: Small, focused functions
def process_order(order_id: str) -> OrderResult:
    order = find_order(order_id)
    validate_stock(order)
    total = calculate_total(order)
    reserve_inventory(order)
    confirm_order(order, total)
    return OrderResult(success=True, total=total)

def find_order(order_id: str) -> Order:
    order = order_repository.find_by_id(order_id)
    if not order:
        raise OrderNotFoundError(order_id)
    return order

def calculate_total(order: Order) -> float:
    total = sum(item.price * item.quantity for item in order.items)
    return apply_discounts(total)
```

### Key Takeaways
- Extract until each function does one thing
- Function names become documentation
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: do_one_thing -->
## 2.2 Do One Thing

### Summary
A function should do one thing, do it well, and do it only. If you can extract another function with a meaningful name, the original is doing more than one thing.

<!-- ANTI_PATTERN -->
```python
# Bad: Validates AND saves AND notifies
def handle_order(order: Order) -> None:
    if not order.items:
        raise ValueError("Empty order")
    if order.total < 0:
        raise ValueError("Invalid total")
    db.save(order)
    email_service.send(order.customer.email, "Order placed!")
```

<!-- REFACTORED -->
```python
# Good: Each function does one thing
def handle_order(order: Order) -> None:
    validate_order(order)
    save_order(order)
    notify_customer(order)

def validate_order(order: Order) -> None:
    if not order.items:
        raise EmptyOrderError()
    if order.total < 0:
        raise InvalidTotalError(order.total)

def save_order(order: Order) -> None:
    order_repository.save(order)

def notify_customer(order: Order) -> None:
    notification_service.send_order_confirmation(order)
```

### Key Takeaways
- "One thing" = one level of abstraction
- If you describe a function with "and", it does too much
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: one_level_of_abstraction -->
## 2.3 One Level of Abstraction per Function

### Summary
Don't mix high-level business logic with low-level implementation details in the same function.

<!-- ANTI_PATTERN -->
```python
# Bad: Mixes high-level flow with low-level SQL
def complete_order(order_id: str) -> None:
    # High level
    order = get_order(order_id)
    # Low level SQL
    cursor.execute(
        "UPDATE inventory SET quantity = quantity - %s WHERE product_id = %s",
        (item.quantity, item.product_id)
    )
    # High level
    charge_customer(order)
    # Low level string formatting
    msg = f"<html><body>Order {order_id} confirmed!</body></html>"
    smtp.send(order.customer.email, msg)
```

<!-- REFACTORED -->
```python
# Good: Consistent abstraction level
def complete_order(order_id: str) -> None:
    order = get_order(order_id)
    reserve_inventory(order)
    charge_customer(order)
    send_confirmation(order)

# Low-level details hidden in their own functions
def reserve_inventory(order: Order) -> None:
    for item in order.items:
        inventory_repository.decrement(item.product_id, item.quantity)

def send_confirmation(order: Order) -> None:
    email = email_builder.build_confirmation(order)
    email_service.send(order.customer.email, email)
```

### Key Takeaways
- Read function top-to-bottom as a narrative
- Each called function is one level down in abstraction
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: function_arguments -->
## 2.4 Function Arguments

### Summary
Fewer arguments are better. Zero (niladic) is best, then one (monadic), then two (dyadic). Three (triadic) requires strong justification. More than three—refactor.

<!-- ANTI_PATTERN -->
```python
# Bad: Too many arguments, hard to remember order
def create_order(
    customer_id, product_id, quantity, shipping_address,
    billing_address, discount_code, gift_wrap, note
):
    ...

# Caller has no idea what these booleans mean
create_order("C1", "P1", 2, "123 St", "456 Ave", None, True, False)
```

<!-- REFACTORED -->
```python
# Good: Use objects to group related arguments
@dataclass
class OrderRequest:
    customer_id: str
    items: list[OrderItem]
    shipping_address: Address
    billing_address: Address
    options: OrderOptions = field(default_factory=OrderOptions)

def create_order(request: OrderRequest) -> Order:
    ...

# Caller is clear
request = OrderRequest(
    customer_id="C1",
    items=[OrderItem(product_id="P1", quantity=2)],
    shipping_address=shipping,
    billing_address=billing
)
create_order(request)
```

### Key Takeaways
- 0-2 arguments: ideal
- 3 arguments: justify it
- 4+ arguments: wrap in a class/dataclass
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: command_query_separation -->
## 2.5 Command-Query Separation

### Summary
A function should either **do something** (command) or **answer something** (query), never both.

<!-- ANTI_PATTERN -->
```python
# Bad: Sets attribute AND returns success status
def set_order_status(order: Order, status: str) -> bool:
    if status in VALID_STATUSES:
        order.status = status
        return True
    return False

# Confusing usage
if set_order_status(order, "shipped"):
    ...
```

<!-- REFACTORED -->
```python
# Good: Separate command and query
def is_valid_status(status: str) -> bool:
    return status in VALID_STATUSES

def set_order_status(order: Order, status: str) -> None:
    if not is_valid_status(status):
        raise InvalidStatusError(status)
    order.status = status

# Clear usage
if is_valid_status(new_status):
    set_order_status(order, new_status)
```

### Key Takeaways
- Commands: return `None`, cause side effects
- Queries: return values, no side effects
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: no_side_effects -->
## 2.6 Avoid Side Effects

### Summary
Side effects are lies. A function that claims to do one thing but secretly modifies global state or input arguments creates hidden bugs.

<!-- ANTI_PATTERN -->
```python
# Bad: Modifies global state and input secretly
session_data = {}

def validate_customer(customer: Customer) -> bool:
    if customer.email and customer.id:
        session_data['current_customer'] = customer  # Hidden side effect!
        customer.validated = True  # Mutates input!
        return True
    return False
```

<!-- REFACTORED -->
```python
# Good: Pure validation, explicit state management
def is_valid_customer(customer: Customer) -> bool:
    return bool(customer.email and customer.id)

def create_session(customer: Customer) -> Session:
    return Session(customer_id=customer.id)

def mark_validated(customer: Customer) -> Customer:
    return Customer(**{**customer.__dict__, 'validated': True})
```

### Key Takeaways
- If a function has side effects, name them explicitly
- Prefer returning new values over mutating inputs
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: dry -->
## 2.7 DRY (Don't Repeat Yourself)

### Summary
Duplication is the root of maintenance evil. Every piece of knowledge should have a single, unambiguous representation.

<!-- ANTI_PATTERN -->
```python
# Bad: Same discount logic duplicated
def calculate_order_total(order: Order) -> float:
    total = sum(item.price * item.quantity for item in order.items)
    if total > 100:
        total *= 0.9  # 10% discount
    return total

def calculate_cart_preview(cart: Cart) -> float:
    total = sum(item.price * item.quantity for item in cart.items)
    if total > 100:
        total *= 0.9  # 10% discount - duplicated!
    return total
```

<!-- REFACTORED -->
```python
# Good: Single source of truth
BULK_DISCOUNT_THRESHOLD = 100
BULK_DISCOUNT_MULTIPLIER = 0.9

def calculate_subtotal(items: list[LineItem]) -> float:
    return sum(item.price * item.quantity for item in items)

def apply_bulk_discount(amount: float) -> float:
    if amount > BULK_DISCOUNT_THRESHOLD:
        return amount * BULK_DISCOUNT_MULTIPLIER
    return amount

def calculate_order_total(order: Order) -> float:
    return apply_bulk_discount(calculate_subtotal(order.items))

def calculate_cart_preview(cart: Cart) -> float:
    return apply_bulk_discount(calculate_subtotal(cart.items))
```

### Key Takeaways
- If you change logic in one place, you shouldn't need to change it elsewhere
- Extract common logic to shared functions
<!-- END_PRINCIPLE -->

---

# Part 3: SOLID Principles

<!-- PRINCIPLE: single_responsibility -->
## 3.1 Single Responsibility Principle (SRP)

### Summary
A class should have one, and only one, reason to change. "Reason to change" = one stakeholder or actor.

<!-- ANTI_PATTERN -->
```python
# Bad: Three reasons to change (order logic, persistence, formatting)
class Order:
    def __init__(self, items: list[OrderItem]):
        self.items = items
    
    def calculate_total(self) -> float:
        return sum(i.price * i.quantity for i in self.items)
    
    def save_to_database(self) -> None:
        db.execute(f"INSERT INTO orders ...")
    
    def generate_invoice_html(self) -> str:
        return f"<html>Invoice: {self.calculate_total()}</html>"
```

<!-- REFACTORED -->
```python
# Good: Each class has one responsibility
class Order:
    def __init__(self, items: list[OrderItem]):
        self.items = items
    
    def calculate_total(self) -> float:
        return sum(i.price * i.quantity for i in self.items)


class OrderRepository:
    def save(self, order: Order) -> None:
        db.execute(f"INSERT INTO orders ...")


class InvoiceGenerator:
    def generate_html(self, order: Order) -> str:
        return f"<html>Invoice: {order.calculate_total()}</html>"
```

### Key Takeaways
- Ask: "What actors depend on this class?"
- If multiple actors → split the class
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: open_closed -->
## 3.2 Open-Closed Principle (OCP)

### Summary
Software entities should be open for extension but closed for modification. Add new behavior without changing existing code.

<!-- ANTI_PATTERN -->
```python
# Bad: Must modify this function for every new discount type
def apply_discount(order: Order, discount_type: str) -> float:
    total = order.calculate_total()
    if discount_type == "percentage":
        return total * 0.9
    elif discount_type == "fixed":
        return total - 10
    elif discount_type == "bogo":  # Added later, modified existing code
        return total * 0.5
    return total
```

<!-- REFACTORED -->
```python
# Good: Open for extension via new classes
from abc import ABC, abstractmethod

class Discount(ABC):
    @abstractmethod
    def apply(self, total: float) -> float:
        pass


class PercentageDiscount(Discount):
    def __init__(self, percent: float):
        self.percent = percent
    
    def apply(self, total: float) -> float:
        return total * (1 - self.percent / 100)


class FixedDiscount(Discount):
    def __init__(self, amount: float):
        self.amount = amount
    
    def apply(self, total: float) -> float:
        return max(0, total - self.amount)


# Adding new discount: just create new class, no modification
class BuyOneGetOneFree(Discount):
    def apply(self, total: float) -> float:
        return total * 0.5


def apply_discount(order: Order, discount: Discount) -> float:
    return discount.apply(order.calculate_total())
```

### Key Takeaways
- Use abstractions (protocols/ABCs) to enable extension
- New requirements = new code, not changed code
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: liskov_substitution -->
## 3.3 Liskov Substitution Principle (LSP)

### Summary
Subtypes must be substitutable for their base types. Code using a base class should work with any derived class without knowing it.

<!-- ANTI_PATTERN -->
```python
# Bad: Subclass breaks parent's contract
class Order:
    def calculate_total(self) -> float:
        return sum(i.price * i.quantity for i in self.items)

class FreeOrder(Order):
    def calculate_total(self) -> float:
        return 0.0  # Might seem fine...

class RefundedOrder(Order):
    def calculate_total(self) -> float:
        raise NotImplementedError("Refunded orders have no total")  # Breaks LSP!

# This code breaks with RefundedOrder
def print_receipt(order: Order) -> None:
    print(f"Total: {order.calculate_total()}")  # Explodes!
```

<!-- REFACTORED -->
```python
# Good: Subtypes honor the contract
class Order:
    def calculate_total(self) -> float:
        return sum(i.price * i.quantity for i in self.items)
    
    def get_display_total(self) -> str:
        return f"${self.calculate_total():.2f}"


class FreeOrder(Order):
    def calculate_total(self) -> float:
        return 0.0


class RefundedOrder(Order):
    def __init__(self, original_total: float):
        self.original_total = original_total
    
    def calculate_total(self) -> float:
        return 0.0  # Valid: returns a float as promised
    
    def get_display_total(self) -> str:
        return f"$0.00 (Refunded from ${self.original_total:.2f})"


# Works with all Order types
def print_receipt(order: Order) -> None:
    print(f"Total: {order.get_display_total()}")
```

### Key Takeaways
- Don't raise exceptions where parent doesn't
- Don't return different types than parent
- Subtypes can do more, but must do at least what parent does
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: interface_segregation -->
## 3.4 Interface Segregation Principle (ISP)

### Summary
Clients should not be forced to depend on interfaces they don't use. Many specific interfaces are better than one general-purpose interface.

<!-- ANTI_PATTERN -->
```python
# Bad: Fat interface forces unnecessary implementations
from abc import ABC, abstractmethod

class OrderProcessor(ABC):
    @abstractmethod
    def create_order(self, order: Order) -> None: ...
    
    @abstractmethod
    def process_payment(self, order: Order) -> None: ...
    
    @abstractmethod
    def send_notification(self, order: Order) -> None: ...
    
    @abstractmethod
    def generate_report(self, order: Order) -> str: ...


# Forced to implement methods it doesn't need
class SimpleOrderCreator(OrderProcessor):
    def create_order(self, order: Order) -> None:
        ...  # Real implementation
    
    def process_payment(self, order: Order) -> None:
        raise NotImplementedError()  # Doesn't do this!
    
    def send_notification(self, order: Order) -> None:
        raise NotImplementedError()  # Doesn't do this!
    
    def generate_report(self, order: Order) -> str:
        raise NotImplementedError()  # Doesn't do this!
```

<!-- REFACTORED -->
```python
# Good: Segregated interfaces
from abc import ABC, abstractmethod

class OrderCreator(ABC):
    @abstractmethod
    def create_order(self, order: Order) -> None: ...


class PaymentProcessor(ABC):
    @abstractmethod
    def process_payment(self, order: Order) -> None: ...


class NotificationSender(ABC):
    @abstractmethod
    def send_notification(self, order: Order) -> None: ...


class ReportGenerator(ABC):
    @abstractmethod
    def generate_report(self, order: Order) -> str: ...


# Only implement what's needed
class SimpleOrderCreator(OrderCreator):
    def create_order(self, order: Order) -> None:
        ...  # Real implementation


# Can combine when needed
class FullOrderService(OrderCreator, PaymentProcessor, NotificationSender):
    def create_order(self, order: Order) -> None: ...
    def process_payment(self, order: Order) -> None: ...
    def send_notification(self, order: Order) -> None: ...
```

### Key Takeaways
- Split fat interfaces into focused ones
- Clients only depend on methods they use
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: dependency_inversion -->
## 3.5 Dependency Inversion Principle (DIP)

### Summary
High-level modules should not depend on low-level modules. Both should depend on abstractions. Abstractions should not depend on details.

<!-- ANTI_PATTERN -->
```python
# Bad: High-level OrderService depends on low-level MySQL and SMTP
class MySQLDatabase:
    def save_order(self, order: Order) -> None:
        ...  # MySQL-specific code

class SMTPEmailer:
    def send(self, to: str, body: str) -> None:
        ...  # SMTP-specific code

class OrderService:
    def __init__(self):
        self.db = MySQLDatabase()  # Hard dependency!
        self.emailer = SMTPEmailer()  # Hard dependency!
    
    def place_order(self, order: Order) -> None:
        self.db.save_order(order)
        self.emailer.send(order.customer.email, "Order placed!")
```

<!-- REFACTORED -->
```python
# Good: Depend on abstractions, inject implementations
from abc import ABC, abstractmethod

class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None: ...


class NotificationService(ABC):
    @abstractmethod
    def notify_order_placed(self, order: Order) -> None: ...


class OrderService:
    def __init__(
        self,
        repository: OrderRepository,
        notifications: NotificationService
    ):
        self.repository = repository
        self.notifications = notifications
    
    def place_order(self, order: Order) -> None:
        self.repository.save(order)
        self.notifications.notify_order_placed(order)


# Implementations
class MySQLOrderRepository(OrderRepository):
    def save(self, order: Order) -> None:
        ...  # MySQL-specific

class EmailNotificationService(NotificationService):
    def notify_order_placed(self, order: Order) -> None:
        ...  # Email-specific

# Injection
service = OrderService(
    repository=MySQLOrderRepository(),
    notifications=EmailNotificationService()
)
```

### Key Takeaways
- Define abstractions at the high level
- Low-level modules implement those abstractions
- Use dependency injection to wire things together
<!-- END_PRINCIPLE -->

---

# Part 4: Error Handling

<!-- PRINCIPLE: exceptions_over_error_codes -->
## 4.1 Use Exceptions Instead of Error Codes

### Summary
Exceptions separate error handling from happy path logic. Error codes clutter code with checks.

<!-- ANTI_PATTERN -->
```python
# Bad: Error codes force checking at every step
def process_order(order_id: str) -> dict:
    result = validate_order(order_id)
    if result['error']:
        return result
    
    result = reserve_inventory(order_id)
    if result['error']:
        return result
    
    result = charge_payment(order_id)
    if result['error']:
        return result
    
    return {'success': True}
```

<!-- REFACTORED -->
```python
# Good: Exceptions for clean happy path
def process_order(order_id: str) -> None:
    try:
        validate_order(order_id)
        reserve_inventory(order_id)
        charge_payment(order_id)
    except ValidationError as e:
        raise OrderProcessingError(f"Validation failed: {e}")
    except InventoryError as e:
        raise OrderProcessingError(f"Inventory issue: {e}")
    except PaymentError as e:
        raise OrderProcessingError(f"Payment failed: {e}")
```

### Key Takeaways
- Happy path reads top-to-bottom without interruption
- Handle errors in dedicated blocks
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: dont_return_none -->
## 4.2 Don't Return None

### Summary
Returning `None` forces callers to check for null constantly. Raise exceptions or return empty collections instead.

<!-- ANTI_PATTERN -->
```python
# Bad: Caller must remember to check for None
def find_order(order_id: str) -> Order | None:
    for order in orders:
        if order.id == order_id:
            return order
    return None

# Easy to forget the check
order = find_order("123")
total = order.calculate_total()  # AttributeError if None!
```

<!-- REFACTORED -->
```python
# Good Option 1: Raise exception
def get_order(order_id: str) -> Order:
    for order in orders:
        if order.id == order_id:
            return order
    raise OrderNotFoundError(order_id)

# Good Option 2: Return empty collection for searches
def find_orders_by_customer(customer_id: str) -> list[Order]:
    return [o for o in orders if o.customer_id == customer_id]  # Empty list, not None

# Good Option 3: Explicit Optional with get_ vs find_ convention
def find_order(order_id: str) -> Order | None:  # find_ signals optional
    ...

def get_order(order_id: str) -> Order:  # get_ signals guaranteed or exception
    order = find_order(order_id)
    if order is None:
        raise OrderNotFoundError(order_id)
    return order
```

### Key Takeaways
- `find_*` can return `None` (searching)
- `get_*` should raise if not found (expecting it exists)
- Collections: return empty, not `None`
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: dont_pass_none -->
## 4.3 Don't Pass None

### Summary
Passing `None` as an argument often indicates missing design. It forces the function to handle a special case.

<!-- ANTI_PATTERN -->
```python
# Bad: None as special case
def calculate_shipping(order: Order, address: Address | None) -> float:
    if address is None:
        return 0.0  # Digital delivery?
    return shipping_calculator.calculate(address)

calculate_shipping(order, None)  # Unclear intent
```

<!-- REFACTORED -->
```python
# Good: Explicit separate functions
def calculate_shipping(order: Order, address: Address) -> float:
    return shipping_calculator.calculate(address)

def is_digital_delivery(order: Order) -> bool:
    return all(item.is_digital for item in order.items)

# Clear intent at call site
if is_digital_delivery(order):
    shipping = 0.0
else:
    shipping = calculate_shipping(order, address)
```

### Key Takeaways
- `None` arguments often mask missing abstractions
- Make the special cases explicit with separate code paths
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: error_handling_one_thing -->
## 4.4 Error Handling Is One Thing

### Summary
A function that handles errors should do that and little else. The `try` block should contain the work, the `except` block only error handling.

<!-- ANTI_PATTERN -->
```python
# Bad: Business logic mixed with error handling
def place_order(order: Order) -> OrderResult:
    try:
        if not order.items:
            raise ValueError("Empty order")
        total = sum(i.price * i.quantity for i in order.items)
        if total > 1000:
            total *= 0.95
        order.total = total
        db.save(order)
        email_service.send(order.customer.email, f"Total: {total}")
        return OrderResult(success=True, total=total)
    except ValueError as e:
        logger.error(f"Validation error: {e}")
        return OrderResult(success=False, error=str(e))
    except DatabaseError as e:
        logger.error(f"DB error: {e}")
        return OrderResult(success=False, error="Database error")
```

<!-- REFACTORED -->
```python
# Good: Separate business logic from error handling wrapper
def place_order(order: Order) -> OrderResult:
    try:
        return _execute_place_order(order)
    except ValidationError as e:
        logger.error(f"Validation error: {e}")
        return OrderResult(success=False, error=str(e))
    except DatabaseError as e:
        logger.error(f"DB error: {e}")
        return OrderResult(success=False, error="Database error")

def _execute_place_order(order: Order) -> OrderResult:
    validate_order(order)
    total = calculate_total(order)
    save_order(order)
    notify_customer(order, total)
    return OrderResult(success=True, total=total)
```

### Key Takeaways
- Extract try body to its own function
- Error handling function wraps and handles
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: exception_context -->
## 4.5 Provide Context in Exceptions

### Summary
Exceptions should carry enough information to diagnose the problem. Include what operation failed and relevant state.

<!-- ANTI_PATTERN -->
```python
# Bad: No context
def reserve_inventory(order: Order) -> None:
    for item in order.items:
        if inventory[item.product_id] < item.quantity:
            raise ValueError("Insufficient stock")  # Which product? How much needed?
```

<!-- REFACTORED -->
```python
# Good: Rich context in custom exception
class InsufficientStockError(Exception):
    def __init__(self, product_id: str, requested: int, available: int):
        self.product_id = product_id
        self.requested = requested
        self.available = available
        super().__init__(
            f"Insufficient stock for product {product_id}: "
            f"requested {requested}, available {available}"
        )

def reserve_inventory(order: Order) -> None:
    for item in order.items:
        available = inventory.get(item.product_id, 0)
        if available < item.quantity:
            raise InsufficientStockError(
                product_id=item.product_id,
                requested=item.quantity,
                available=available
            )
```

### Key Takeaways
- Create domain-specific exception classes
- Include relevant IDs, quantities, states
- Make the message actionable
<!-- END_PRINCIPLE -->

---

# Part 5: Boundaries

<!-- PRINCIPLE: law_of_demeter -->
## 5.1 Law of Demeter

### Summary
Only talk to your immediate friends. Don't reach through objects to access their internals. Method `m` of class `C` should only call methods on: `C` itself, `m`'s parameters, objects created in `m`, `C`'s direct components.

<!-- ANTI_PATTERN -->
```python
# Bad: Train wreck - reaching through multiple objects
def get_shipping_city(order: Order) -> str:
    return order.customer.address.city.name

def apply_regional_discount(order: Order) -> float:
    if order.customer.address.country.tax_rate > 0.2:
        return order.total * 0.9
    return order.total
```

<!-- REFACTORED -->
```python
# Good: Ask, don't dig
class Order:
    def get_shipping_city_name(self) -> str:
        return self.shipping_address.city_name
    
    def get_regional_tax_rate(self) -> float:
        return self.shipping_address.regional_tax_rate

class Address:
    @property
    def city_name(self) -> str:
        return self.city.name
    
    @property
    def regional_tax_rate(self) -> float:
        return self.country.tax_rate

# Clean usage
def get_shipping_city(order: Order) -> str:
    return order.get_shipping_city_name()

def apply_regional_discount(order: Order) -> float:
    if order.get_regional_tax_rate() > 0.2:
        return order.total * 0.9
    return order.total
```

### Key Takeaways
- One dot good, many dots bad (usually)
- Push behavior to where the data lives
- Exceptions: fluent interfaces, data structures
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: encapsulate_third_party -->
## 5.2 Encapsulate Third-Party Code

### Summary
Wrap third-party libraries behind your own interfaces. This limits the blast radius of changes and makes testing easier.

<!-- ANTI_PATTERN -->
```python
# Bad: Third-party API scattered throughout codebase
import stripe

def charge_order(order: Order) -> None:
    stripe.api_key = "sk_..."
    stripe.Charge.create(
        amount=int(order.total * 100),
        currency="usd",
        source=order.payment_source,
        metadata={"order_id": order.id}
    )

def refund_order(order: Order) -> None:
    stripe.api_key = "sk_..."
    charges = stripe.Charge.list(metadata={"order_id": order.id})
    stripe.Refund.create(charge=charges.data[0].id)
```

<!-- REFACTORED -->
```python
# Good: Wrapped behind clean interface
from abc import ABC, abstractmethod

class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: float, source: str, reference: str) -> str: ...
    
    @abstractmethod
    def refund(self, charge_id: str) -> None: ...


class StripeGateway(PaymentGateway):
    def __init__(self, api_key: str):
        self.api_key = api_key
    
    def charge(self, amount: float, source: str, reference: str) -> str:
        import stripe
        stripe.api_key = self.api_key
        result = stripe.Charge.create(
            amount=int(amount * 100),
            currency="usd",
            source=source,
            metadata={"reference": reference}
        )
        return result.id
    
    def refund(self, charge_id: str) -> None:
        import stripe
        stripe.api_key = self.api_key
        stripe.Refund.create(charge=charge_id)


# Business logic uses abstraction
def charge_order(order: Order, gateway: PaymentGateway) -> None:
    charge_id = gateway.charge(order.total, order.payment_source, order.id)
    order.charge_id = charge_id
```

### Key Takeaways
- Wrap at the boundary, not at every use
- Your interface reflects your domain, not theirs
- Easy to swap implementations or mock for tests
<!-- END_PRINCIPLE -->

---

# Part 6: Comments

<!-- PRINCIPLE: good_comments -->
## 6.1 Good Comments

### Summary
Some comments are necessary: legal notices, explaining intent, clarifying obscure code, warnings, TODOs.

<!-- REFACTORED -->
```python
# Legal comment (necessary)
# Copyright 2024 Acme Corp. All rights reserved.
# Licensed under MIT License.

# Intent explanation (why, not what)
def calculate_total(order: Order) -> float:
    total = sum(item.price * item.quantity for item in order.items)
    # Apply early-bird discount for orders placed before 9 AM
    # per marketing campaign MKT-2024-001
    if order.placed_at.hour < 9:
        total *= 0.85
    return total

# Warning of consequences
def clear_all_orders() -> None:
    # WARNING: This purges production data. Only for use in testing.
    order_repository.delete_all()

# TODO with ticket reference
def send_notification(order: Order) -> None:
    # TODO(JIRA-1234): Add SMS notification support
    email_service.send(order.customer.email, "Order confirmed")

# Clarifying regex
def extract_order_id(text: str) -> str:
    # Pattern: ORD-YYYYMMDD-XXXXX (e.g., ORD-20240115-A1B2C)
    match = re.search(r'ORD-\d{8}-[A-Z0-9]{5}', text)
    return match.group(0) if match else ""
```

### Key Takeaways
- Legal, intent, warning, TODO = often necessary
- Explain WHY, not WHAT
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: bad_comments -->
## 6.2 Bad Comments

### Summary
Most comments are code smells: redundant, misleading, noise, or commented-out code. If you need a comment, first try to improve the code.

<!-- ANTI_PATTERN -->
```python
# Bad: Redundant - says exactly what code says
# Increment counter by one
counter += 1

# Bad: Misleading - comment lies
# Returns the order total
def calculate_total(order: Order) -> float:
    return order.subtotal  # Actually returns subtotal, not total!

# Bad: Noise - adds nothing
# Default constructor
def __init__(self):
    pass

# Bad: Journal comments - use version control
# 2024-01-15: Added discount feature
# 2024-01-20: Fixed bug in discount calculation
# 2024-01-22: Refactored discount logic
def apply_discount(total: float) -> float:
    ...

# Bad: Commented-out code - delete it
def process_order(order: Order) -> None:
    validate(order)
    # old_calculation = order.subtotal * 1.1
    # if old_calculation > 100:
    #     old_calculation *= 0.9
    charge(order)
```

<!-- REFACTORED -->
```python
# Good: Code speaks for itself
counter += 1

# Good: Name matches behavior
def calculate_subtotal(order: Order) -> float:
    return order.subtotal

# Good: Use git for history, delete dead code
def apply_discount(total: float, discount_percent: float) -> float:
    return total * (1 - discount_percent / 100)

def process_order(order: Order) -> None:
    validate(order)
    charge(order)
```

### Key Takeaways
- Comment needing to explain WHAT = refactor the code
- Version history = git, not comments
- Dead code = delete it
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: self_documenting_code -->
## 6.3 Self-Documenting Code

### Summary
The best comment is code that doesn't need one. Use intention-revealing names, extract explanatory functions, and use named constants.

<!-- ANTI_PATTERN -->
```python
# Bad: Comment compensates for poor naming
def proc(o, f):
    # Check if order qualifies for free shipping
    # Orders over $100 get free shipping
    if o.t > 100 and f:
        return 0
    # Calculate shipping based on weight
    # $5 base + $2 per kg
    return 5 + o.w * 2
```

<!-- REFACTORED -->
```python
# Good: Code explains itself
FREE_SHIPPING_THRESHOLD = 100
BASE_SHIPPING_COST = 5
COST_PER_KG = 2

def calculate_shipping(order: Order, free_shipping_eligible: bool) -> float:
    if qualifies_for_free_shipping(order, free_shipping_eligible):
        return 0
    return calculate_weight_based_shipping(order)

def qualifies_for_free_shipping(order: Order, eligible: bool) -> bool:
    return order.total > FREE_SHIPPING_THRESHOLD and eligible

def calculate_weight_based_shipping(order: Order) -> float:
    return BASE_SHIPPING_COST + order.weight_kg * COST_PER_KG
```

### Key Takeaways
- Extract conditions to named functions
- Extract magic numbers to named constants
- Rename until the comment is unnecessary
<!-- END_PRINCIPLE -->

---

# Part 7: Testing

<!-- PRINCIPLE: first_tests -->
## 7.1 F.I.R.S.T. Principles

### Summary
Tests should be: **Fast** (milliseconds), **Independent** (no shared state), **Repeatable** (same result every run), **Self-validating** (pass/fail, no manual inspection), **Timely** (written before or with the code).

<!-- ANTI_PATTERN -->
```python
# Bad: Slow, not independent, not repeatable
class TestOrder:
    _shared_order = None  # Shared state!
    
    def test_create_order(self):
        TestOrder._shared_order = Order(items=[...])  # Slow DB call
        db.save(TestOrder._shared_order)
    
    def test_order_total(self):
        # Depends on test_create_order running first!
        assert TestOrder._shared_order.calculate_total() == 100
    
    def test_external_api(self):
        # Calls real external service - not repeatable!
        result = payment_gateway.charge(TestOrder._shared_order)
        print(f"Check result manually: {result}")  # Not self-validating!
```

<!-- REFACTORED -->
```python
# Good: Fast, independent, repeatable, self-validating
class TestOrder:
    def test_calculate_total_sums_items(self):
        order = Order(items=[
            OrderItem(price=10, quantity=2),
            OrderItem(price=5, quantity=1)
        ])
        assert order.calculate_total() == 25
    
    def test_calculate_total_empty_order(self):
        order = Order(items=[])
        assert order.calculate_total() == 0
    
    def test_payment_processing(self):
        gateway = FakePaymentGateway()  # Test double
        order = Order(items=[OrderItem(price=100, quantity=1)])
        
        charge_order(order, gateway)
        
        assert gateway.charges == [100]
```

### Key Takeaways
- No shared mutable state between tests
- Use test doubles for external services
- Assert, don't print
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: one_concept_per_test -->
## 7.2 One Concept Per Test

### Summary
Each test should verify one concept. Multiple asserts are fine if they test facets of the same concept.

<!-- ANTI_PATTERN -->
```python
# Bad: Multiple concepts in one test
def test_order():
    # Concept 1: Creation
    order = Order(customer_id="C1")
    assert order.customer_id == "C1"
    
    # Concept 2: Adding items
    order.add_item(OrderItem(product_id="P1", quantity=2))
    assert len(order.items) == 1
    
    # Concept 3: Total calculation
    assert order.calculate_total() == 20
    
    # Concept 4: Discount application
    order.apply_discount(PercentageDiscount(10))
    assert order.calculate_total() == 18
```

<!-- REFACTORED -->
```python
# Good: Separate tests for separate concepts
def test_order_stores_customer_id():
    order = Order(customer_id="C1")
    assert order.customer_id == "C1"

def test_add_item_increases_item_count():
    order = Order(customer_id="C1")
    order.add_item(OrderItem(product_id="P1", quantity=2))
    assert len(order.items) == 1

def test_calculate_total_sums_item_prices():
    order = Order(customer_id="C1")
    order.add_item(OrderItem(product_id="P1", price=10, quantity=2))
    assert order.calculate_total() == 20

def test_percentage_discount_reduces_total():
    order = Order(customer_id="C1")
    order.add_item(OrderItem(product_id="P1", price=100, quantity=1))
    order.apply_discount(PercentageDiscount(10))
    assert order.calculate_total() == 90
```

### Key Takeaways
- One failing test = one broken concept
- Test names document behavior
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: arrange_act_assert -->
## 7.3 Arrange-Act-Assert (Given-When-Then)

### Summary
Structure tests in three clear phases: set up the scenario, perform the action, verify the outcome.

<!-- ANTI_PATTERN -->
```python
# Bad: Phases mixed together
def test_order_discount():
    order = Order()
    order.add_item(OrderItem(price=100, quantity=1))
    assert len(order.items) == 1  # Assert in middle?
    total_before = order.calculate_total()
    order.apply_discount(PercentageDiscount(10))
    order.add_item(OrderItem(price=50, quantity=1))  # More arranging after act?
    assert order.calculate_total() == 135
```

<!-- REFACTORED -->
```python
# Good: Clear AAA structure
def test_percentage_discount_reduces_total():
    # Arrange
    order = Order()
    order.add_item(OrderItem(price=100, quantity=1))
    order.add_item(OrderItem(price=50, quantity=1))
    
    # Act
    order.apply_discount(PercentageDiscount(10))
    
    # Assert
    assert order.calculate_total() == 135

# Also good: Given-When-Then style
def test_bulk_discount_applied_over_threshold():
    # Given an order over the bulk threshold
    order = create_order_with_total(150)
    
    # When bulk discount is calculated
    discounted = apply_bulk_discount(order.total)
    
    # Then 10% discount is applied
    assert discounted == 135
```

### Key Takeaways
- Separate setup, action, and verification
- One act per test (usually)
- Comments optional if code is clear
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: test_readability -->
## 7.4 Test Readability

### Summary
Tests are documentation. Use helper functions to keep tests expressive and focused on intent, not mechanics.

<!-- ANTI_PATTERN -->
```python
# Bad: Setup noise obscures intent
def test_premium_customer_gets_discount():
    customer = Customer(
        id="C1",
        email="test@example.com",
        name="Test User",
        created_at=datetime(2020, 1, 1),
        tier="premium",
        address=Address(
            street="123 Main St",
            city="Springfield",
            country="US"
        )
    )
    order = Order(
        id="O1",
        customer=customer,
        items=[
            OrderItem(product_id="P1", name="Widget", price=100, quantity=1)
        ],
        created_at=datetime.now()
    )
    
    total = calculate_total_with_customer_discount(order)
    
    assert total == 90
```

<!-- REFACTORED -->
```python
# Good: Helpers reveal intent
def test_premium_customer_gets_ten_percent_discount():
    customer = create_premium_customer()
    order = create_order(customer=customer, total=100)
    
    discounted_total = calculate_total_with_customer_discount(order)
    
    assert discounted_total == 90


# Test helpers (in conftest.py or test utilities)
def create_premium_customer(**overrides) -> Customer:
    defaults = {"id": "C1", "tier": "premium", "email": "test@example.com"}
    return Customer(**{**defaults, **overrides})

def create_order(customer: Customer = None, total: float = 100) -> Order:
    customer = customer or create_customer()
    item = OrderItem(product_id="P1", price=total, quantity=1)
    return Order(id="O1", customer=customer, items=[item])
```

### Key Takeaways
- Test code is real code—refactor it too
- Builder/factory helpers reduce noise
- Test name + body should read like a spec
<!-- END_PRINCIPLE -->

---

# Part 8: Component Principles (Cohesion)

<!-- PRINCIPLE: rep -->
## 8.1 Reuse/Release Equivalence Principle (REP)

### Summary
The granule of reuse is the granule of release. Classes that are reused together should be released together and versioned together.

<!-- ANTI_PATTERN -->
```python
# Bad: order_utils.py has unrelated utilities
# Cannot reuse payment functions without pulling in email functions

# order_utils.py
def calculate_order_total(order): ...
def validate_payment_info(payment): ...
def format_email_body(order): ...
def generate_pdf_invoice(order): ...
def send_sms_notification(phone, message): ...
```

<!-- REFACTORED -->
```python
# Good: Cohesive modules that can be reused/released independently

# pricing.py
def calculate_order_total(order): ...
def apply_discount(total, discount): ...
def calculate_tax(total, region): ...

# payment.py
def validate_payment_info(payment): ...
def process_payment(payment, amount): ...

# notifications.py
def send_email(to, subject, body): ...
def send_sms(phone, message): ...

# documents.py
def generate_pdf_invoice(order): ...
def generate_packing_slip(order): ...
```

### Key Takeaways
- Group classes that are reused together
- If you release it together, package it together
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: ccp -->
## 8.2 Common Closure Principle (CCP)

### Summary
Classes that change for the same reason at the same time should be grouped together. Classes that change at different times or for different reasons should be separated.

<!-- ANTI_PATTERN -->
```python
# Bad: pricing.py changes when pricing OR tax OR discount rules change
# Three different reasons to change in one module

# pricing.py
class PriceCalculator:
    def calculate(self, items): ...

class TaxCalculator:  # Changes when tax law changes
    def calculate(self, total, region): ...

class DiscountEngine:  # Changes when marketing changes
    def apply(self, total, customer_tier): ...
```

<!-- REFACTORED -->
```python
# Good: Separated by reason for change

# pricing/base.py - Changes when base pricing logic changes
class PriceCalculator:
    def calculate(self, items) -> float: ...

# pricing/tax.py - Changes when tax regulations change
class TaxCalculator:
    def calculate(self, total: float, region: str) -> float: ...

# pricing/discounts.py - Changes when marketing/promotions change
class DiscountEngine:
    def apply(self, total: float, customer_tier: str) -> float: ...

# pricing/service.py - Coordinates, rarely changes
class PricingService:
    def __init__(self, price_calc, tax_calc, discount_engine):
        self.price_calc = price_calc
        self.tax_calc = tax_calc
        self.discount_engine = discount_engine
    
    def calculate_final_price(self, order) -> float:
        subtotal = self.price_calc.calculate(order.items)
        discounted = self.discount_engine.apply(subtotal, order.customer.tier)
        return self.tax_calc.calculate(discounted, order.region)
```

### Key Takeaways
- SRP at the component level
- Changes should be localized to one module
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: crp -->
## 8.3 Common Reuse Principle (CRP)

### Summary
Don't force users to depend on things they don't use. If you use one class from a module, you should use (or at least be compatible with) all classes in that module.

<!-- ANTI_PATTERN -->
```python
# Bad: Importing order_utils pulls in heavy dependencies
# Even if you only need calculate_total

# order_utils.py
import pandas  # Heavy!
import reportlab  # Heavy!
import stripe  # External API!

def calculate_total(order): ...  # Simple math
def generate_pdf_report(orders): ...  # Needs reportlab
def export_to_excel(orders): ...  # Needs pandas
def process_payment(order): ...  # Needs stripe

# User just wants calculate_total but gets all dependencies
from order_utils import calculate_total
```

<!-- REFACTORED -->
```python
# Good: Split so users only depend on what they need

# order/totals.py - No external dependencies
def calculate_total(order): ...
def calculate_subtotal(items): ...

# order/reports.py - Only import if you need reports
import pandas
import reportlab
def generate_pdf_report(orders): ...
def export_to_excel(orders): ...

# order/payment.py - Only import if you need payment
import stripe
def process_payment(order): ...

# User gets just what they need
from order.totals import calculate_total  # Clean, no heavy deps
```

### Key Takeaways
- Don't pollute simple modules with heavy dependencies
- Users shouldn't pay for what they don't use
<!-- END_PRINCIPLE -->

---

# Part 9: Component Principles (Coupling)

<!-- PRINCIPLE: adp -->
## 9.1 Acyclic Dependencies Principle (ADP)

### Summary
The dependency graph of components must have no cycles. Cycles make systems hard to build, test, and release independently.

<!-- ANTI_PATTERN -->
```python
# Bad: Circular dependency
# orders.py
from payments import process_payment  # orders depends on payments

class Order:
    def complete(self):
        process_payment(self)

# payments.py
from orders import Order  # payments depends on orders - CYCLE!

def process_payment(order: Order):
    order.status = "paid"
```

<!-- REFACTORED -->
```python
# Good: Break cycle with dependency inversion

# order.py - No dependency on payments
class Order:
    def __init__(self):
        self.status = "pending"
    
    def mark_paid(self):
        self.status = "paid"


# payment_processor.py - Depends on Order, not vice versa
from order import Order

class PaymentProcessor:
    def process(self, order: Order) -> None:
        # ... payment logic ...
        order.mark_paid()


# Alternative: Use an interface/callback
# order.py
class Order:
    def complete(self, payment_handler):
        payment_handler(self)
        self.status = "completed"

# payments.py
def handle_payment(order):
    # Process payment, no import of Order needed at module level
    pass
```

### Key Takeaways
- Draw your dependency graph; find the cycles
- Break cycles with DIP or callbacks
- Consider if shared code should be extracted
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: sdp -->
## 9.2 Stable Dependencies Principle (SDP)

### Summary
Depend in the direction of stability. A component should only depend on components more stable than itself.

Stability = (outgoing dependencies) / (incoming + outgoing dependencies)
- Stable component: many dependents, few dependencies (hard to change)
- Unstable component: few dependents, many dependencies (easy to change)

<!-- ANTI_PATTERN -->
```python
# Bad: Stable core depends on unstable UI helpers

# core/order.py (stable - everything depends on this)
from ui.formatters import format_currency  # Depends on unstable UI code!

class Order:
    def get_display_total(self) -> str:
        return format_currency(self.total)

# ui/formatters.py (unstable - changes often with UI)
def format_currency(amount: float) -> str:
    return f"${amount:.2f}"
```

<!-- REFACTORED -->
```python
# Good: Stable core has no outward dependencies

# core/order.py (stable)
class Order:
    def get_total(self) -> float:
        return self.total

# ui/formatters.py (unstable - depends on stable core)
from core.order import Order

def format_order_total(order: Order) -> str:
    return f"${order.get_total():.2f}"

# If core needs formatting, inject it
# core/order.py
class Order:
    def get_display_total(self, formatter) -> str:
        return formatter(self.total)
```

### Key Takeaways
- Stable = many incoming deps, few outgoing
- Unstable components should depend on stable ones
- Don't let stable code depend on unstable code
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: sap -->
## 9.3 Stable Abstractions Principle (SAP)

### Summary
A component should be as abstract as it is stable. Stable components should contain abstractions (interfaces). Unstable components should contain implementations.

<!-- ANTI_PATTERN -->
```python
# Bad: Stable component with concrete implementations
# Everyone depends on this, but it's all concrete

# core/payment.py (stable - many depend on it)
import stripe

class PaymentProcessor:
    def process(self, amount: float) -> bool:
        stripe.Charge.create(amount=amount)  # Concrete!
        return True
```

<!-- REFACTORED -->
```python
# Good: Stable component is abstract

# core/payment.py (stable - abstract)
from abc import ABC, abstractmethod

class PaymentProcessor(ABC):
    @abstractmethod
    def process(self, amount: float) -> bool:
        pass


# infrastructure/stripe_payment.py (unstable - concrete)
import stripe
from core.payment import PaymentProcessor

class StripePaymentProcessor(PaymentProcessor):
    def process(self, amount: float) -> bool:
        stripe.Charge.create(amount=amount)
        return True


# Main zone (SAP plot: stable + abstract in upper left)
# - core/payment.py: stable, abstract ✓
# - infrastructure/stripe_payment.py: unstable, concrete ✓
```

### Key Takeaways
- Stable + Concrete = Zone of Pain (hard to change)
- Unstable + Abstract = Zone of Uselessness (no one uses it)
- Target: Stable+Abstract or Unstable+Concrete
<!-- END_PRINCIPLE -->

---

# Part 10: Clean Architecture

<!-- PRINCIPLE: dependency_rule -->
## 10.1 The Dependency Rule

### Summary
Source code dependencies must point only inward. Nothing in an inner circle can know anything about something in an outer circle.

```
┌─────────────────────────────────────────┐
│           Frameworks & Drivers          │  ← Outer (details)
│  ┌─────────────────────────────────┐    │
│  │      Interface Adapters         │    │
│  │  ┌─────────────────────────┐    │    │
│  │  │      Use Cases          │    │    │
│  │  │  ┌─────────────────┐    │    │    │
│  │  │  │    Entities     │    │    │    │  ← Inner (policies)
│  │  │  └─────────────────┘    │    │    │
│  │  └─────────────────────────┘    │    │
│  └─────────────────────────────────┘    │
└─────────────────────────────────────────┘
```

<!-- ANTI_PATTERN -->
```python
# Bad: Inner layer (entity) knows about outer layer (database)
# entities/order.py
import sqlite3  # Framework concern in entity!

class Order:
    def save(self):
        conn = sqlite3.connect('orders.db')
        conn.execute("INSERT INTO orders ...")  # Entity knows about DB!
```

<!-- REFACTORED -->
```python
# Good: Dependencies point inward

# entities/order.py (innermost - knows nothing about outer layers)
class Order:
    def __init__(self, id: str, customer_id: str, items: list):
        self.id = id
        self.customer_id = customer_id
        self.items = items
    
    def calculate_total(self) -> float:
        return sum(item.price * item.quantity for item in self.items)


# use_cases/place_order.py (knows about entities, not frameworks)
from entities.order import Order

class PlaceOrderUseCase:
    def __init__(self, order_repository, payment_gateway):
        self.order_repository = order_repository  # Abstract!
        self.payment_gateway = payment_gateway    # Abstract!
    
    def execute(self, order: Order) -> None:
        self.payment_gateway.charge(order.calculate_total())
        self.order_repository.save(order)


# adapters/repositories.py (knows about use case interfaces)
from use_cases.interfaces import OrderRepository

class SQLiteOrderRepository(OrderRepository):
    def save(self, order: Order) -> None:
        # SQLite details here, outer layer
        ...


# frameworks/database.py (outermost - framework details)
import sqlite3
# Actual SQLite connection handling
```

### Key Takeaways
- Entities: business rules, no dependencies
- Use Cases: application rules, depend on entities
- Adapters: convert data, depend on use cases
- Frameworks: details, depend on adapters
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: entities -->
## 10.2 Entities

### Summary
Entities encapsulate enterprise-wide business rules. They are the most stable and least likely to change when external things change.

<!-- ANTI_PATTERN -->
```python
# Bad: Entity mixed with application/framework concerns
class Order:
    def __init__(self, data: dict):  # Coupled to dict format
        self.id = data['id']
        self.items = data['items']
    
    def calculate_total(self) -> float:
        return sum(i['price'] * i['qty'] for i in self.items)
    
    def to_json(self) -> str:  # Serialization doesn't belong here
        import json
        return json.dumps({'id': self.id, 'total': self.calculate_total()})
    
    def save(self, db):  # Persistence doesn't belong here
        db.execute("INSERT INTO orders ...")
```

<!-- REFACTORED -->
```python
# Good: Pure entity with only business rules
from dataclasses import dataclass

@dataclass
class OrderItem:
    product_id: str
    price: float
    quantity: int
    
    def line_total(self) -> float:
        return self.price * self.quantity


@dataclass
class Order:
    id: str
    customer_id: str
    items: list[OrderItem]
    
    def calculate_total(self) -> float:
        return sum(item.line_total() for item in self.items)
    
    def add_item(self, item: OrderItem) -> None:
        self.items.append(item)
    
    def is_empty(self) -> bool:
        return len(self.items) == 0
```

### Key Takeaways
- No framework imports in entities
- No I/O (database, network, file) in entities
- Only business logic and rules
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: use_cases -->
## 10.3 Use Cases

### Summary
Use cases contain application-specific business rules. They orchestrate entities and define the flow for specific operations.

<!-- ANTI_PATTERN -->
```python
# Bad: Use case knows about frameworks
import sqlite3
from flask import request

class PlaceOrderUseCase:
    def execute(self):
        data = request.json  # Knows about Flask!
        order = Order(**data)
        conn = sqlite3.connect('db.sqlite')  # Knows about SQLite!
        conn.execute("INSERT INTO orders ...")
```

<!-- REFACTORED -->
```python
# Good: Use case depends only on abstractions
from abc import ABC, abstractmethod
from entities.order import Order

class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None: ...

class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: float, source: str) -> str: ...

class NotificationService(ABC):
    @abstractmethod
    def send_order_confirmation(self, order: Order) -> None: ...


@dataclass
class PlaceOrderRequest:
    customer_id: str
    items: list[OrderItem]
    payment_source: str


@dataclass
class PlaceOrderResponse:
    order_id: str
    total: float
    success: bool


class PlaceOrderUseCase:
    def __init__(
        self,
        repository: OrderRepository,
        payment: PaymentGateway,
        notifications: NotificationService
    ):
        self.repository = repository
        self.payment = payment
        self.notifications = notifications
    
    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        order = Order(
            id=generate_id(),
            customer_id=request.customer_id,
            items=request.items
        )
        
        self.payment.charge(order.calculate_total(), request.payment_source)
        self.repository.save(order)
        self.notifications.send_order_confirmation(order)
        
        return PlaceOrderResponse(
            order_id=order.id,
            total=order.calculate_total(),
            success=True
        )
```

### Key Takeaways
- Use cases define input/output boundaries (DTOs)
- Depend on abstract interfaces, not implementations
- Orchestrate entities, don't contain business rules
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: interface_adapters -->
## 10.4 Interface Adapters

### Summary
Adapters convert data between the format used by use cases/entities and the format used by external agencies (database, web, etc.).

<!-- REFACTORED -->
```python
# Good: Adapters convert between inner and outer formats

# adapters/repositories/sql_order_repository.py
from entities.order import Order, OrderItem
from use_cases.interfaces import OrderRepository

class SQLOrderRepository(OrderRepository):
    def __init__(self, connection):
        self.connection = connection
    
    def save(self, order: Order) -> None:
        self.connection.execute(
            "INSERT INTO orders (id, customer_id, total) VALUES (?, ?, ?)",
            (order.id, order.customer_id, order.calculate_total())
        )
        for item in order.items:
            self.connection.execute(
                "INSERT INTO order_items (order_id, product_id, qty, price) VALUES (?, ?, ?, ?)",
                (order.id, item.product_id, item.quantity, item.price)
            )
    
    def find_by_id(self, order_id: str) -> Order:
        row = self.connection.execute(
            "SELECT * FROM orders WHERE id = ?", (order_id,)
        ).fetchone()
        items = self._load_items(order_id)
        return Order(id=row['id'], customer_id=row['customer_id'], items=items)


# adapters/controllers/order_controller.py
from use_cases.place_order import PlaceOrderUseCase, PlaceOrderRequest

class OrderController:
    def __init__(self, place_order_use_case: PlaceOrderUseCase):
        self.place_order = place_order_use_case
    
    def create_order(self, http_request: dict) -> dict:
        # Convert HTTP format to use case format
        request = PlaceOrderRequest(
            customer_id=http_request['customer_id'],
            items=[OrderItem(**i) for i in http_request['items']],
            payment_source=http_request['payment_token']
        )
        
        # Execute use case
        response = self.place_order.execute(request)
        
        # Convert use case format to HTTP format
        return {
            'order_id': response.order_id,
            'total': response.total,
            'status': 'success' if response.success else 'failed'
        }
```

### Key Takeaways
- Presenters convert use case output to view format
- Controllers convert input to use case format
- Repositories convert entities to/from persistence format
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: screaming_architecture -->
## 10.5 Screaming Architecture

### Summary
Architecture should scream its intent. Looking at the top-level directory structure should tell you what the system does, not what frameworks it uses.

<!-- ANTI_PATTERN -->
```
# Bad: Screams "Rails!" not "Order System!"
my_app/
├── controllers/
│   ├── application_controller.py
│   └── orders_controller.py
├── models/
│   ├── order.py
│   └── customer.py
├── views/
│   └── orders/
└── routes.py
```

<!-- REFACTORED -->
```
# Good: Screams "Order Processing System!"
order_system/
├── orders/
│   ├── entities/
│   │   └── order.py
│   ├── use_cases/
│   │   ├── place_order.py
│   │   └── cancel_order.py
│   └── interfaces/
│       └── order_repository.py
├── customers/
│   ├── entities/
│   │   └── customer.py
│   └── use_cases/
│       └── register_customer.py
├── payments/
│   ├── interfaces/
│   │   └── payment_gateway.py
│   └── use_cases/
│       └── process_payment.py
└── infrastructure/
    ├── persistence/
    │   └── sql_repositories.py
    └── web/
        └── http_controllers.py
```

### Key Takeaways
- Top-level = business capabilities (orders, customers, payments)
- Frameworks hidden in infrastructure/
- New developer sees the domain, not the framework
<!-- END_PRINCIPLE -->

<!-- PRINCIPLE: humble_object -->
## 10.6 Humble Object Pattern

### Summary
Separate hard-to-test code from easy-to-test code. Keep the hard-to-test part as simple (humble) as possible, pushing logic into testable objects.

<!-- ANTI_PATTERN -->
```python
# Bad: Hard-to-test view logic mixed with presentation
class OrderView:
    def render(self, order: Order) -> str:
        # Business logic in view!
        total = sum(i.price * i.quantity for i in order.items)
        if total > 100:
            discount = total * 0.1
            total -= discount
        
        # Formatting mixed with logic
        html = f"<div class='order'>"
        html += f"<h1>Order {order.id}</h1>"
        for item in order.items:
            html += f"<p>{item.name}: ${item.price * item.quantity}</p>"
        html += f"<p class='total'>Total: ${total:.2f}</p>"
        html += f"</div>"
        return html
```

<!-- REFACTORED -->
```python
# Good: Logic in testable presenter, view is humble

# Presenter: Easy to test, contains all logic
@dataclass
class OrderViewModel:
    order_id: str
    line_items: list[dict]  # {name, formatted_total}
    formatted_total: str

class OrderPresenter:
    def present(self, order: Order) -> OrderViewModel:
        total = order.calculate_total()
        return OrderViewModel(
            order_id=order.id,
            line_items=[
                {'name': i.name, 'formatted_total': f'${i.line_total():.2f}'}
                for i in order.items
            ],
            formatted_total=f'${total:.2f}'
        )

# View: Humble, no logic, hard to test but trivially correct
class OrderView:
    def render(self, vm: OrderViewModel) -> str:
        html = f"<div class='order'>"
        html += f"<h1>Order {vm.order_id}</h1>"
        for item in vm.line_items:
            html += f"<p>{item['name']}: {item['formatted_total']}</p>"
        html += f"<p class='total'>Total: {vm.formatted_total}</p>"
        html += f"</div>"
        return html


# Test the presenter easily
def test_presenter_formats_total():
    order = Order(id="O1", items=[OrderItem(price=100, quantity=1)])
    vm = OrderPresenter().present(order)
    assert vm.formatted_total == "$100.00"
```

### Key Takeaways
- Hard-to-test: GUIs, databases, external services
- Humble objects: simple, obvious, little logic
- Push logic into testable objects (presenters, gateways)
<!-- END_PRINCIPLE -->

---

# Part 11: Multi-File Architecture Example

<!-- MULTI_FILE_EXAMPLE -->
## Complete Clean Architecture Example

This example demonstrates a complete order processing system following all principles.

### Directory Structure

```
order_system/
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   ├── order.py
│   │   └── customer.py
│   └── value_objects/
│       ├── __init__.py
│       └── money.py
├── application/
│   ├── __init__.py
│   ├── interfaces/
│   │   ├── __init__.py
│   │   ├── order_repository.py
│   │   └── payment_gateway.py
│   └── use_cases/
│       ├── __init__.py
│       └── place_order.py
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── in_memory_order_repository.py
│   └── payment/
│       ├── __init__.py
│       └── fake_payment_gateway.py
├── adapters/
│   ├── __init__.py
│   └── controllers/
│       ├── __init__.py
│       └── order_controller.py
└── main.py
```

### File Contents

**domain/value_objects/money.py**
```python
from dataclasses import dataclass


@dataclass(frozen=True)
class Money:
    amount: float
    currency: str = "USD"
    
    def add(self, other: "Money") -> "Money":
        if self.currency != other.currency:
            raise ValueError("Cannot add different currencies")
        return Money(self.amount + other.amount, self.currency)
    
    def multiply(self, factor: float) -> "Money":
        return Money(self.amount * factor, self.currency)
    
    def __str__(self) -> str:
        return f"{self.currency} {self.amount:.2f}"
```

**domain/entities/order.py**
```python
from dataclasses import dataclass, field
from typing import List
from domain.value_objects.money import Money


@dataclass
class OrderItem:
    product_id: str
    product_name: str
    unit_price: Money
    quantity: int
    
    def line_total(self) -> Money:
        return self.unit_price.multiply(self.quantity)


@dataclass
class Order:
    id: str
    customer_id: str
    items: List[OrderItem] = field(default_factory=list)
    status: str = "pending"
    
    def add_item(self, item: OrderItem) -> None:
        self.items.append(item)
    
    def calculate_total(self) -> Money:
        if not self.items:
            return Money(0)
        total = Money(0)
        for item in self.items:
            total = total.add(item.line_total())
        return total
    
    def mark_paid(self) -> None:
        if self.status != "pending":
            raise ValueError(f"Cannot pay order in status: {self.status}")
        self.status = "paid"
    
    def is_empty(self) -> bool:
        return len(self.items) == 0
```

**application/interfaces/order_repository.py**
```python
from abc import ABC, abstractmethod
from domain.entities.order import Order


class OrderRepository(ABC):
    @abstractmethod
    def save(self, order: Order) -> None:
        pass
    
    @abstractmethod
    def find_by_id(self, order_id: str) -> Order:
        pass
```

**application/interfaces/payment_gateway.py**
```python
from abc import ABC, abstractmethod
from domain.value_objects.money import Money


class PaymentGateway(ABC):
    @abstractmethod
    def charge(self, amount: Money, payment_source: str) -> str:
        """Returns charge ID on success, raises PaymentError on failure."""
        pass


class PaymentError(Exception):
    pass
```

**application/use_cases/place_order.py**
```python
from dataclasses import dataclass
from typing import List
from domain.entities.order import Order, OrderItem
from domain.value_objects.money import Money
from application.interfaces.order_repository import OrderRepository
from application.interfaces.payment_gateway import PaymentGateway, PaymentError


@dataclass
class PlaceOrderRequest:
    order_id: str
    customer_id: str
    items: List[dict]  # [{product_id, product_name, unit_price, quantity}]
    payment_source: str


@dataclass
class PlaceOrderResponse:
    success: bool
    order_id: str = ""
    total: str = ""
    error: str = ""


class PlaceOrderUseCase:
    def __init__(
        self,
        order_repository: OrderRepository,
        payment_gateway: PaymentGateway
    ):
        self.order_repository = order_repository
        self.payment_gateway = payment_gateway
    
    def execute(self, request: PlaceOrderRequest) -> PlaceOrderResponse:
        try:
            order = self._create_order(request)
            self._validate_order(order)
            self._process_payment(order, request.payment_source)
            self._save_order(order)
            return self._success_response(order)
        except (ValueError, PaymentError) as e:
            return PlaceOrderResponse(success=False, error=str(e))
    
    def _create_order(self, request: PlaceOrderRequest) -> Order:
        order = Order(id=request.order_id, customer_id=request.customer_id)
        for item_data in request.items:
            item = OrderItem(
                product_id=item_data["product_id"],
                product_name=item_data["product_name"],
                unit_price=Money(item_data["unit_price"]),
                quantity=item_data["quantity"]
            )
            order.add_item(item)
        return order
    
    def _validate_order(self, order: Order) -> None:
        if order.is_empty():
            raise ValueError("Cannot place empty order")
    
    def _process_payment(self, order: Order, payment_source: str) -> None:
        self.payment_gateway.charge(order.calculate_total(), payment_source)
        order.mark_paid()
    
    def _save_order(self, order: Order) -> None:
        self.order_repository.save(order)
    
    def _success_response(self, order: Order) -> PlaceOrderResponse:
        return PlaceOrderResponse(
            success=True,
            order_id=order.id,
            total=str(order.calculate_total())
        )
```

**infrastructure/persistence/in_memory_order_repository.py**
```python
from domain.entities.order import Order
from application.interfaces.order_repository import OrderRepository


class InMemoryOrderRepository(OrderRepository):
    def __init__(self):
        self._orders: dict[str, Order] = {}
    
    def save(self, order: Order) -> None:
        self._orders[order.id] = order
    
    def find_by_id(self, order_id: str) -> Order:
        order = self._orders.get(order_id)
        if order is None:
            raise KeyError(f"Order not found: {order_id}")
        return order
```

**infrastructure/payment/fake_payment_gateway.py**
```python
from domain.value_objects.money import Money
from application.interfaces.payment_gateway import PaymentGateway, PaymentError


class FakePaymentGateway(PaymentGateway):
    def __init__(self):
        self.charges: list[dict] = []
        self.should_fail: bool = False
    
    def charge(self, amount: Money, payment_source: str) -> str:
        if self.should_fail:
            raise PaymentError("Payment declined")
        
        charge_id = f"ch_{len(self.charges) + 1}"
        self.charges.append({
            "id": charge_id,
            "amount": amount,
            "source": payment_source
        })
        return charge_id
```

**adapters/controllers/order_controller.py**
```python
from application.use_cases.place_order import PlaceOrderUseCase, PlaceOrderRequest


class OrderController:
    def __init__(self, place_order_use_case: PlaceOrderUseCase):
        self.place_order_use_case = place_order_use_case
    
    def create_order(self, http_request: dict) -> dict:
        request = PlaceOrderRequest(
            order_id=http_request["order_id"],
            customer_id=http_request["customer_id"],
            items=http_request["items"],
            payment_source=http_request["payment_source"]
        )
        
        response = self.place_order_use_case.execute(request)
        
        if response.success:
            return {
                "status": "success",
                "data": {
                    "order_id": response.order_id,
                    "total": response.total
                }
            }
        else:
            return {
                "status": "error",
                "message": response.error
            }
```

**main.py**
```python
from infrastructure.persistence.in_memory_order_repository import InMemoryOrderRepository
from infrastructure.payment.fake_payment_gateway import FakePaymentGateway
from application.use_cases.place_order import PlaceOrderUseCase
from adapters.controllers.order_controller import OrderController


def main():
    # Wire up dependencies (normally done by DI container)
    order_repository = InMemoryOrderRepository()
    payment_gateway = FakePaymentGateway()
    
    place_order_use_case = PlaceOrderUseCase(
        order_repository=order_repository,
        payment_gateway=payment_gateway
    )
    
    controller = OrderController(place_order_use_case)
    
    # Simulate HTTP request
    http_request = {
        "order_id": "ORD-001",
        "customer_id": "CUST-001",
        "items": [
            {"product_id": "PROD-1", "product_name": "Widget", "unit_price": 29.99, "quantity": 2},
            {"product_id": "PROD-2", "product_name": "Gadget", "unit_price": 49.99, "quantity": 1}
        ],
        "payment_source": "tok_visa_4242"
    }
    
    result = controller.create_order(http_request)
    print(result)


if __name__ == "__main__":
    main()
```

**tests/test_place_order.py**
```python
from domain.entities.order import Order, OrderItem
from domain.value_objects.money import Money
from application.use_cases.place_order import PlaceOrderUseCase, PlaceOrderRequest
from infrastructure.persistence.in_memory_order_repository import InMemoryOrderRepository
from infrastructure.payment.fake_payment_gateway import FakePaymentGateway


class TestPlaceOrder:
    def setup_method(self):
        self.repository = InMemoryOrderRepository()
        self.payment_gateway = FakePaymentGateway()
        self.use_case = PlaceOrderUseCase(self.repository, self.payment_gateway)
    
    def test_places_order_successfully(self):
        request = PlaceOrderRequest(
            order_id="ORD-001",
            customer_id="CUST-001",
            items=[{"product_id": "P1", "product_name": "Test", "unit_price": 100, "quantity": 1}],
            payment_source="tok_test"
        )
        
        response = self.use_case.execute(request)
        
        assert response.success is True
        assert response.order_id == "ORD-001"
        assert response.total == "USD 100.00"
    
    def test_fails_for_empty_order(self):
        request = PlaceOrderRequest(
            order_id="ORD-002",
            customer_id="CUST-001",
            items=[],
            payment_source="tok_test"
        )
        
        response = self.use_case.execute(request)
        
        assert response.success is False
        assert "empty" in response.error.lower()
    
    def test_fails_when_payment_declined(self):
        self.payment_gateway.should_fail = True
        request = PlaceOrderRequest(
            order_id="ORD-003",
            customer_id="CUST-001",
            items=[{"product_id": "P1", "product_name": "Test", "unit_price": 100, "quantity": 1}],
            payment_source="tok_test"
        )
        
        response = self.use_case.execute(request)
        
        assert response.success is False
        assert "declined" in response.error.lower()
```
<!-- END_MULTI_FILE_EXAMPLE -->

---

# Appendix: Quick Reference Checklist

## Before Writing Code
- [ ] Does the name reveal intent?
- [ ] Is the function doing one thing?
- [ ] Are arguments minimal (0-2 ideal)?
- [ ] Does the class have one reason to change?

## While Writing Code
- [ ] Dependencies point inward?
- [ ] Am I mixing abstraction levels?
- [ ] Can I extract a well-named function?
- [ ] Am I repeating logic elsewhere?

## Error Handling
- [ ] Using exceptions, not error codes?
- [ ] Returning empty collections, not null?
- [ ] Do exceptions have context?
- [ ] Is error handling separated from logic?

## Before Committing
- [ ] Would I need a comment to explain this? (If yes, refactor)
- [ ] Are there any long method chains? (Law of Demeter)
- [ ] Is third-party code wrapped?
- [ ] Do tests cover one concept each?

## Architecture Check
- [ ] Do folder names describe the domain, not the framework?
- [ ] Are entities free of framework imports?
- [ ] Are use cases framework-agnostic?
- [ ] Can I swap the database without touching business logic?

---

<!-- DOCUMENT_END -->
