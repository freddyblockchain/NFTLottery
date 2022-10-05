from pyteal import *
import json

# Create an expression to store 0 in the `Count` global variable and return 1
handle_creation = Seq(
    App.globalPut(Bytes("CurrentRandom"), Global.zero_address()),
    App.globalPut(Bytes("Participants"), Int(0)),
    App.globalPut(Bytes("Ongoing"), Int(0)),
    App.globalPut(Bytes("LotteryRound"), Int(0)),
    App.globalPut(Bytes("IntVersion"), Int(0)),
    Approve()
)

# Main router class
router = Router(
    # Name of the contract
    "my-first-router",
    # What to do for each on-complete type when no arguments are passed (bare call)
    BareCallActions(
        # On create only, just approve
        no_op=OnCompleteAction.create_only(handle_creation),
        # Always let creator update/delete but only by the creator of this contract
        update_application=OnCompleteAction.always(Reject()),
        delete_application=OnCompleteAction.always(Reject()),
        # No local state, don't bother handling it.
        close_out=OnCompleteAction.never(),   # Equivalent to omitting completely
        opt_in=OnCompleteAction.never(),      # Equivalent to omitting completely
        clear_state=OnCompleteAction.never(),  # Equivalent to omitting completely
    ),
)

@router.method(no_op=CallConfig.CALL)
def resolveLottery() -> Expr:
    return Seq(
        Assert(Global.round() >= App.globalGet(Bytes("LotteryRound"))),
        App.globalPut(Bytes("Ongoing"), Int(0)),
    )

@router.method(no_op=CallConfig.CALL)
def startLottery() -> Expr:
    return Seq(
        Assert(App.globalGet(Bytes("Ongoing")) == Int(0)),
        App.globalPut(Bytes("LotteryRound"), Add(Global.round(), Int(10))),
        App.globalPut(Bytes("Ongoing"), Int(1)),
    )

@router.method(no_op=CallConfig.CALL)
def getRandomNumber(random_contract_call: abi.Application,*,output: abi.DynamicBytes) -> Expr:
    return Seq(
        Assert(App.globalGet(Bytes("Ongoing")) == Int(1)),
        Assert(random_contract_call.application_id() == Int(110096026)),
        Assert(Global.round() >= App.globalGet(Bytes("LotteryRound"))),

        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.MethodCall(
        app_id=random_contract_call.application_id(),
        method_signature="get(uint64,byte[])byte[]",
        args=[Itob(App.globalGet(Bytes("LotteryRound"))),Bytes("base32", "7Z5PWO2C6LFNQFGHWKSK5H47IQP5OJW2M3HA2QPXTY3WTNP5NU2MHBW27M")]
        ),
        InnerTxnBuilder.Submit(),

        App.globalPut(Bytes("CurrentRandom"), InnerTxn.last_log()),
        App.globalPut(Bytes("Ongoing"), Int(0)),
        App.globalPut(Bytes("IntVersion"), Btoi(Substring(App.globalGet(Bytes("CurrentRandom")), Int(8), Int(16)))),

        output.set(App.globalGet(Bytes('CurrentRandom')))
    )


approval_program, clear_state_program, contract = router.compile_program(
    version=7, optimize=OptimizeOptions(scratch_slots=True)
)

if __name__ == "__main__":
    with open("build/lottery_contract.teal", "w") as f:
        f.write(approval_program)

    with open("build/lottery_contract_state.teal", "w") as f:
        f.write(clear_state_program)

    with open("build/lottery_contract.json", "w") as f:
        f.write(json.dumps(contract.dictify(), indent=4))
