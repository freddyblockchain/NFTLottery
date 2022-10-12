from pyteal import *
import json

# Create an expression to store 0 in the `Count` global variable and return 1
handle_creation = Seq(
    App.globalPut(Bytes("Participants"), Int(0)),
    App.globalPut(Bytes("Ongoing"), Int(0)),
    App.globalPut(Bytes("LotteryRound"), Int(0)),
    App.globalPut(Bytes("Winner"), Int(0)),
    App.globalPut(Bytes("LotteryResolved"), Int(0)),
    Approve()
)

# Main router class
router = Router(
    "my-first-router",
    BareCallActions(
        no_op=OnCompleteAction.create_only(handle_creation),
        update_application=OnCompleteAction.always(Reject()),
        delete_application=OnCompleteAction.always(Reject()),
        close_out=OnCompleteAction.never(),
        opt_in=OnCompleteAction.always(Approve()),     
        clear_state=OnCompleteAction.never(),  
    ),
)

@router.method(no_op=CallConfig.CALL)
def resetLottery(*,output: abi.String) -> Expr:
    """Use this method for when the winner does not claim his/her reward, and the lottery is blocked."""
    return Seq (
        Assert(App.globalGet(Bytes("Ongoing")) == Int(1)),
        Assert(Global.round() >= App.globalGet(Bytes("LotteryRound")) + Int(50)),
        App.globalPut(Bytes("Participants"), Int(0)),
        App.globalPut(Bytes("Ongoing"), Int(0)),
        App.globalPut(Bytes("LotteryResolved"), Int(0)),
        output.set("lottery is reset!")
    )

@router.method(no_op=CallConfig.CALL)
def claimWin(*,output: abi.String) -> Expr:
    return Seq (
        Assert(App.globalGet(Bytes("Ongoing")) == Int(1)),
        Assert(App.globalGet(Bytes("LotteryResolved")) == Int(1)),
        Assert(App.localGet(Txn.sender(), Bytes("ParticipantNumber")) == App.globalGet(Bytes("Winner"))),
        Assert(App.localGet(Txn.sender(), Bytes("ParticipantLotteryRound")) == App.globalGet(Bytes("LotteryRound"))),
        App.globalPut(Bytes("LotteryResolved"), Int(0)),
        App.globalPut(Bytes("Participants"), Int(0)),
        App.globalPut(Bytes("Ongoing"), Int(0)),
        output.set("you are the winner!")
    )
@router.method(no_op=CallConfig.CALL)
def resolveLottery(random_contract_call: abi.Application,*,output: abi.DynamicBytes) -> Expr:
    return Seq(
        Assert(App.globalGet(Bytes("Ongoing")) == Int(1)),
        Assert(App.globalGet(Bytes("LotteryResolved")) == Int(0)),
        Assert(random_contract_call.application_id() == Int(110096026)),
        Assert(Global.round() >= App.globalGet(Bytes("LotteryRound"))),

        InnerTxnBuilder.Begin(),
        InnerTxnBuilder.MethodCall(
        app_id=random_contract_call.application_id(),
        method_signature="get(uint64,byte[])byte[]",
        args=[Itob(App.globalGet(Bytes("LotteryRound"))),Bytes("base32", "7Z5PWO2C6LFNQFGHWKSK5H47IQP5OJW2M3HA2QPXTY3WTNP5NU2MHBW27M")]
        ),
        InnerTxnBuilder.Submit(),

        App.globalPut(Bytes("RandomNumber"), Btoi(Substring(InnerTxn.last_log(), Int(8), Int(16)))),
        App.globalPut(Bytes("Winner"), App.globalGet(Bytes("RandomNumber")) % App.globalGet(Bytes("Participants"))),
        App.globalPut(Bytes("LotteryResolved"), Int(1)),

        output.set(App.globalGet(Bytes('Winner'))),
    )
   

@router.method(no_op=CallConfig.CALL)
def participate() -> Expr:
    return Seq(
        Assert(App.globalGet(Bytes("Ongoing")) == Int(1)),
        Assert(Global.round() <= App.globalGet(Bytes("LotteryRound"))),
        App.localPut(Txn.sender(), Bytes("ParticipantNumber"), App.globalGet(Bytes("Participants"))),
        App.localPut(Txn.sender(), Bytes("ParticipantLotteryRound"), App.globalGet(Bytes("LotteryRound"))),
        App.globalPut(Bytes("Participants"), App.globalGet(Bytes("Participants")) + Int(1)),
    )    

@router.method(no_op=CallConfig.CALL)
def startLottery() -> Expr:
    return Seq(
        Assert(App.globalGet(Bytes("Ongoing")) == Int(0)),
        App.globalPut(Bytes("LotteryRound"), Global.round() +  Int(10)),
        App.globalPut(Bytes("Ongoing"), Int(1)),
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
