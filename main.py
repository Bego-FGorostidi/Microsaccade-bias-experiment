"""
Main script for running the 'microsaccade bias' experiment
made by Anna van Harmelen, 2023

see README.md for instructions if needed
"""

# Import necessary stuff
from psychopy import core
import pandas as pd
from participantinfo import get_participant_details
from set_up import get_monitor_and_dir, get_settings
from eyetracker import Eyelinker
from trial import single_trial, generate_trial_characteristics
from time import time
from numpy import mean
from practice import practice
import datetime as dt
from block import (
    create_trial_list,
    create_blocks,
    block_break,
    long_break,
    finish,
    quick_finish,
)

N_BLOCKS = 20
TRIALS_PER_BLOCK = 40
PREDICTABILITY = 80


def main():
    """
    Data formats / storage:
     - eyetracking data saved in one .edf file per session
     - all trial data saved in one .csv per session
     - subject data in one .csv (for all sessions combined)
    """

    # Set whether this is a test run or not
    testing = False

    # Get monitor and directory information
    monitor, directory = get_monitor_and_dir(testing)

    # Get participant details and save in same file as before
    old_participants = pd.read_csv(
        rf"{directory}\participantinfo.csv",
        dtype={
            "participant_number": int,
            "session_number": int,
            "age": int,
            "trials_completed": str,
        },
    )
    new_participants = get_participant_details(old_participants, testing)

    # Initialise set-up
    settings = get_settings(monitor, directory)
    settings["keyboard"].clearEvents()

    # Connect to eyetracker and calibrate it
    if not testing:
        eyelinker = Eyelinker(
            new_participants.participant_number.iloc[-1],
            new_participants.session_number.iloc[-1],
            settings["window"],
            settings["directory"],
        )
        eyelinker.calibrate()

    # Start recording eyetracker
    if not testing:
        eyelinker.start()

    # Practice until participant wants to stop
    practice(testing, settings)

    # Initialise some stuff
    start_of_experiment = time()
    data = []
    current_trial = 0
    finished_early = True
    block_number = 0

    # Pseudo-randomly create conditions and target locations (so they're weighted)
    n_invalid_trials = N_BLOCKS * TRIALS_PER_BLOCK * (100 - PREDICTABILITY) // 100
    n_valid_trials = N_BLOCKS * TRIALS_PER_BLOCK * PREDICTABILITY // 100
    invalid_trials = create_trial_list(n_invalid_trials, "invalid")
    valid_trials = create_trial_list(n_valid_trials, "valid")
    blocks = create_blocks(
        valid_trials, invalid_trials, N_BLOCKS, TRIALS_PER_BLOCK, PREDICTABILITY
    )

    # Start experiment
    try:
        for block in blocks:
            # Update block number
            block_number += 1

            # Create temporary variable for saving block performance
            block_performance = []

            # Run trials per pseudo-randomly created info
            for target_location, direction, trial_length, congruency in (
                block[0:10] if testing else block
            ):
                current_trial += 1
                start_time = time()

                trial_characteristics: dict = generate_trial_characteristics(
                    congruency, target_location, trial_length, direction
                )

                # Generate trial
                report: dict = single_trial(
                    **trial_characteristics,
                    settings=settings,
                    testing=testing,
                    eyetracker=None if testing else eyelinker,
                )
                end_time = time()

                # Save trial data
                data.append(
                    {
                        "trial_number": current_trial,
                        "block": block_number,
                        "start_time": str(
                            dt.timedelta(seconds=(start_time - start_of_experiment))
                        ),
                        "end_time": str(
                            dt.timedelta(seconds=(end_time - start_of_experiment))
                        ),
                        **trial_characteristics,
                        **report,
                    }
                )

                block_performance.append(report["correct_key"])

            # Calculate average performance score for most recent block
            avg_score = round(mean(block_performance) * 100)

            # Break after end of block, unless it's the last block.
            # Experimenter can re-calibrate the eyetracker by pressing 'c' here.
            calibrated = True
            if block_number == N_BLOCKS // 2:
                while calibrated:
                    calibrated = long_break(
                        N_BLOCKS,
                        avg_score,
                        settings,
                        eyetracker=None if testing else eyelinker,
                    )
                if not testing:
                    eyelinker.start()
            elif block_number < N_BLOCKS:
                while calibrated:
                    calibrated = block_break(
                        block_number,
                        N_BLOCKS,
                        avg_score,
                        settings,
                        eyetracker=None if testing else eyelinker,
                    )

        finished_early = False

    except Exception as e:
        if not isinstance(e, KeyboardInterrupt):
            print(e)

    finally:
        # Stop eyetracker (this should also save the data)
        if not testing:
            eyelinker.stop()

        # Save all collected trial data to a new .csv
        pd.DataFrame(data).to_csv(
            rf"{settings['directory']}\data_session_{new_participants.session_number.iloc[-1]}{'_test' if testing else ''}.csv",
            index=False,
        )

        # Register how many trials this participant has completed
        new_participants.loc[new_participants.index[-1], "trials_completed"] = str(
            len(data)
        )

        # Save participant data to existing .csv file
        new_participants.to_csv(
            rf"{settings['directory']}\participantinfo.csv", index=False
        )

        # Done!
        if finished_early:
            quick_finish(settings)
        else:
            # Thanks for meedoen
            finish(N_BLOCKS, settings)

        core.quit()


if __name__ == "__main__":
    main()
