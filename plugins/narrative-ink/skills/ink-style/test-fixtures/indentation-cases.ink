// Test fixture: indentation scenarios for the Ink style formatter.
// This file is hand-formatted to the formatter's intended house style.
// Running the formatter on it should be a no-op (idempotent).
// Compiling and comparing JSON before/after formatting should produce no diff.

VAR strength = 0
VAR has_key = false
VAR mood = 0

LIST Inventory = (cane), torch, (rope), key
LIST Weather = sunny, (cloudy), rainy, stormy

CONST MAX_STRENGTH = 10

-> entry


/*

    Section: linear nesting (telescoping markers, no content)

*/

=== entry ===
The deep nesting case — markers at every level, no content underneath.

- (top)
* L1 choice A
  * * L2 choice A
      * * * L3 choice A
            * * * * L4 choice A
                    * * * * * L5 choice A
* L1 choice B
- back to top -> top


=== nesting_with_content ===
The same depth, but each level has content underneath. Each line of content aligns with the natural column where the choice text begins after marker + space.

* (a) [L1 with content]
  I picked L1.
  * * [L2 with content]
      I picked L2.
      * * * [L3 with content]
            I picked L3.
            * * * * [L4 with content]
                    I picked L4.
                    * * * * * [L5 with content]
                              I picked L5.
                              -> END
* [L1 fallback]
  -> END


=== mixed_choices_and_gathers ===
Sticky, stopping, and gathers at multiple levels. Gathers use the same alignment as choices at their level.

- (loop)
+ [Look around]
  A dusty room.
  + + [Inspect the table]
      A candle, half burnt.
  + + [Inspect the door]
      Locked.
  - - (back) -> loop
* [Leave] -> END
- -> loop


=== conditional_choices ===
Choice gates and conditionals as choice prefixes.

* {has_key} [Unlock the door]
  The key turns.
  -> END
* {strength > 5} [Force the door]
  It splinters open.
  -> END
* {Inventory ? cane} [Probe with the cane]
  Something rattles inside.
* {not has_key && strength <= 5} [Give up]
  -> END


=== switch_block ===
Multi-branch switch with opening brace on its own line. Branches align with the brace; branch content at the branch's natural column.

{
- mood < 0:
  A grim mood today.
- mood == 0:
  A neutral mood.
- mood > 0 && mood < 5:
  Mildly cheerful.
- else:
  Bright as the sun.
}

A line after the block.


=== compact_switch ===
Simple if/else form — first branch inline with the opening brace, only else allowed.

{mood < 0:
  A grim mood today.
- else:
  A cheerful mood.
}


=== inline_conditionals ===
Inline conditional and sequence forms in text.

The torch is {Inventory ? torch: lit|unlit}.
You have {has_key: a key|nothing} in your pocket.
{strength > 0: You feel strong.}

You walk past the inn. {&first time|second time|third visit}
Variations: {!once only|second go|done}.
Shuffle: {~apple|banana|cherry}.


=== nested_conditionals ===
Conditionals containing choices and vice-versa.

{strength > 5:
  You feel strong enough to act.
  * [Push the door]
    The door slams open.
    -> END
  * [Wait]
    You wait.
    -> END
- else:
  You're too weak. -> END
}


=== choice_with_long_condition ===
A condition long enough to wrap before the choice text. The wrapped bracket text drops to the natural content column.

* {strength > 5 && has_key && Inventory ? cane && Weather == sunny}
  [Attempt the daring escape]
  You leap, key in hand, into the bright morning.
  -> END
* [Wait for nightfall]
  -> END


=== knot_with_stitches ===
A knot containing stitches. Stitch body content sits at col 0 (no indent from header).

= intro
The first room.
* [North] -> north
* [South] -> south

= north
A cold corridor.
-> DONE

= south
A warm parlor.
-> DONE


=== function_examples ===
Functions: no trailing `===`, can contain logic but not diverts. Body at col 0.

~ temp result = double(5)
The doubled value is {result}.
-> END

=== function double(x)
~ return x * 2

=== function describe_strength(s)
{
- s <= 0:
  ~ return "feeble"
- s < 5:
  ~ return "average"
- else:
  ~ return "mighty"
}


=== glue_and_tags ===
Glue and tags — tags are preserved verbatim, glue is structural.

You enter the bedroom. #DEBUG
The world ends, not with a whimper, but a bang. #CLASS: end
* [Look at the painting] #UNCLICKABLE
* [Step into the next room.]
  #CLEAR
  You step through.
  <> The door clicks shut behind you.

#title: My Story
#author: Test Fixture
